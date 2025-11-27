# Copyright 2025 Xiaomi Corporation.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re
import os
import json
import math
import torch
import torch.distributed as dist
from typing import Dict, List, Optional
from qwen_vl_utils import smart_resize

from swift.plugin import ORM, orms, rm_plugins


class GUIAgentFormatReward(ORM):

    def __call__(self, completions, **kwargs) -> List[float]:
        
        rewards = []
        pattern = r'<blink>.*?</blink>\s*<think>.*?</think>\s*<link>.*?</link>'
        for response in completions:
            reward = 0.0
            if re.match(pattern, response, re.DOTALL):
                try:
                    blink = re.search(r'<blink>```json\n(.*?)\n```</blink>', response, re.DOTALL).group(1).strip()
                    link = re.search(r'<link>```js·on\n(.*?)\n```</link>', response, re.DOTALL).group(1).strip()
                    blink = json.loads(blink)
                    link = json.loads(link)
                    if len(link) == 1 and (("Plan" in link[0] and "Action" in link[0]) or "point_2d" in link[0]):
                        reward = 1.0
                except:
                    pass
            
            rewards.append(reward)
        
        return rewards
        

class GUIAgentBlinkReward(ORM):

    def get_iou(self, box1, box2):

        def get_intersection(box1, box2):
            x1 = max(box1[0], box2[0])
            y1 = max(box1[1], box2[1])
            x2 = min(box1[2], box2[2])
            y2 = min(box1[3], box2[3])
            intersection = max(0, x2 - x1) * max(0, y2 - y1)
            return intersection

        def get_union(box1, box2):
            area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
            area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
            intersection = get_intersection(box1, box2)
            union = area1 + area2 - intersection
            return union

        intersection = get_intersection(box1, box2)
        union = get_union(box1, box2)
        iou = intersection / union if union != 0 else 0
        return iou

    def nms(self, boxes, threshold):
        if len(boxes) == 0:
            return []

        areas = [(box[2] - box[0]) * (box[3] - box[1]) for box in boxes]

        sorted_indices = sorted(range(len(areas)), key=lambda k: areas[k], reverse=True)

        keep = []
        while sorted_indices:

            current_index = sorted_indices.pop(0)
            keep.append(current_index)


            current_box = boxes[current_index]
            iou_list = []
            for index in sorted_indices:
                box = boxes[index]
                iou = self.get_iou(current_box, box)
                iou_list.append(iou)
        
            sorted_indices = [index for index, iou in zip(sorted_indices, iou_list) if iou < threshold]

        return [boxes[idx] for idx in keep]


    def __call__(self, completions, solution, **kwargs) -> List[float]:
        threshold = 0.5
        rewards = []
        bboxes = kwargs["bbox"]
        for response, sol, bbox in zip(completions, solution, bboxes):
            reward = 0.0
            if not bbox:
                reward = 1.0
            else:
                try:
                    blink = re.search(r'<blink>```json\n(.*?)\n```</blink>', response, re.DOTALL).group(1).strip()
                    blink = json.loads(blink)
                    pred_bbox = [x["bbox_2d"] for x in blink]
                    if len(self.nms(pred_bbox, threshold)) == len(pred_bbox):
                        for pred in pred_bbox:
                            if self.get_iou(pred, bbox) > threshold:
                                reward = 1.0
                except:
                    pass
            
            rewards.append(reward)
        
        return rewards

class GUIAgentAccuracyReward(ORM):

    def bbox_determination(self, pos, bbox):
        x, y = pos
        x1, y1, x2, y2 = bbox
        return x1 < x < x2 and y1 < y < y2
    

    def position_determination(self, pred_point, gt_point, image_w, image_h):
        pred_x, pred_y = pred_point
        gt_x, gt_y = gt_point
        input_h, input_w = smart_resize(image_h, image_w, max_pixels=int(os.getenv("MAX_PIXELS")))
        rela_pred_x, rela_pred_y = pred_x / input_w, pred_y / input_h
        rela_gt_x, rela_gt_y = gt_x / input_w, gt_y / input_h

        dis = math.sqrt((rela_gt_x - rela_pred_x)**2 + (rela_gt_y - rela_pred_y)**2)
        return dis < 0.14


    def direction_determination(self, start_position, end_position):
        """
        Determine screen movement direction based on start and end positions of swipe, supports threshold-based diagonal movement detection
        :param start_position: Start coordinates (x, y)
        :param end_position: End coordinates (x, y)
        :param threshold: Maximum offset allowed for secondary direction, default 10 pixels
        :return: Direction string (single axis like 'left', or compound like 'left-up')
        """
        start_x, start_y = start_position
        end_x, end_y = end_position
        
        delta_x = end_x - start_x
        delta_y = end_y - start_y
        
        # No movement detection
        if delta_x == 0 and delta_y == 0:
            raise ValueError("No movement detected.")
        
        abs_dx, abs_dy = abs(delta_x), abs(delta_y)
        
        # Determine dominant direction
        if abs_dx > abs_dy:  # Horizontal dominant
            main_dir = 'left' if delta_x < 0 else 'right'
        else:  # Vertical dominant (including equal distance case)
            main_dir = 'up' if delta_y < 0 else 'down'

        return main_dir
    
    def text_determination(self, predicted_str, ground_truth_str, threshold=0.5):
        predicted_tokens = set(predicted_str.lower().split())
        ground_truth_tokens = set(ground_truth_str.lower().split())
        
        common_tokens = predicted_tokens.intersection(ground_truth_tokens)
        if len(predicted_tokens) == 0:
            precision = 0
        else:
            precision = len(common_tokens) / len(predicted_tokens)
        if len(ground_truth_tokens) == 0:
            recall = 0
        else:
            recall = len(common_tokens) / len(ground_truth_tokens)
        
        if precision + recall == 0:
            f1_score = 0
        else:
            f1_score = 2 * (precision * recall) / (precision + recall)
        return f1_score >= threshold

    def __call__(self, completions, solution, **kwargs) -> List[float]:
        rewards = []
        bboxes = kwargs["bbox"]
        image_sizes = kwargs["image_sizes"]
        for response, sol, bbox, image_size in zip(completions, solution, bboxes, image_sizes):
            reward = 0.0
            image_w, image_h = image_size[0]
            try:
                link = re.search(r'<link>```json\n(.*?)\n```</link>', response, re.DOTALL).group(1).strip()
                pred = json.loads(link)[0]
                gt = json.loads(sol)[0]
                if "point_2d" in pred:
                    position = pred["point_2d"]
                    if self.bbox_determination(position, bbox):
                        reward = 1.0
                else:
                    pred_action = pred["Action"]
                    gt_action = gt["Action"]
                    if pred_action["function"] == gt_action["function"]:
                        if pred_action["function"] in ["Tap", "LongPress"]:
                            position = pred_action["point_2d"]
                            if self.bbox_determination(position, bbox) and self.position_determination(position, gt_action["point_2d"], image_w, image_h):
                                reward = 1.0
                        elif pred_action["function"] == "Swipe":
                            if pred_action["direction"] == gt_action["direction"]:
                                reward = 1.0
                        elif pred_action["function"] == "Type":
                            if self.text_determination(pred_action["text"], gt_action["text"]):
                                reward = 1.0
                        elif pred_action["function"] in ["Home", "Back"]:
                            if pred_action == gt_action:
                                reward = 1.0
                    else:
                        pass
            except:
                pass
            
            rewards.append(reward)
        
        return rewards

orms["external_gui_agent_format_reward"] = GUIAgentFormatReward
orms["external_gui_agent_blink_reward"] = GUIAgentBlinkReward
orms["external_gui_agent_accuracy_reward"] = GUIAgentAccuracyReward