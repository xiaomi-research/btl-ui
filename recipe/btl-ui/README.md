# Recipe for BTL-UI

## Verifiable Rewards of BTL-UI

This recipe provides three reward functions for evaluating GUI agent performance in the BTL-UI framework:

### 1. GUIAgentFormatReward (`external_gui_agent_format_reward`)

**Purpose**: Validates the correct format of agent responses.

**Functionality**:
- Checks if the response follows the required XML-like format: `<blink>`, `<think>`, and `<link>` tags
- Validates that the content within `<blink>` and `<link>` tags are valid JSON
- Ensures the link contains either a "Plan" and "Action" structure or a "point_2d" coordinate
- Returns a reward of 1.0 for properly formatted responses, 0.0 otherwise

**Use Case**: Format validation for structured agent outputs in GUI automation tasks.

### 2. GUIAgentBlinkReward (`external_gui_agent_blink_reward`)

**Purpose**: Evaluates the accuracy of bounding box predictions for UI element detection.

**Functionality**:
- Extracts bounding box predictions from the `<blink>` tag in agent responses
- Applies Non-Maximum Suppression (NMS) to remove overlapping detections
- Calculates Intersection over Union (IoU) between predicted and ground truth bounding boxes
- Uses a threshold of 0.5 for IoU comparison
- Returns a reward of 1.0 if at least one predicted box has sufficient overlap with the ground truth, 0.0 otherwise
- Automatically gives full reward (1.0) when no ground truth bounding box is provided

**Use Case**: Object detection accuracy evaluation for UI elements in screen understanding tasks.

### 3. GUIAgentAccuracyReward (`external_gui_agent_accuracy_reward`)

**Purpose**: Comprehensive evaluation of agent action accuracy across different interaction types.

**Functionality**:
- **Point Detection**: Validates if predicted coordinates fall within the correct bounding box
- **Position Accuracy**: Measures distance between predicted and ground truth coordinates using relative positioning
- **Direction Detection**: For swipe actions, validates movement direction (left, right, up, down)
- **Text Matching**: For typing actions, uses F1-score to evaluate text similarity
- **Action Matching**: Validates that the correct action type is performed (Tap, LongPress, Swipe, Type, Home, Back)

**Key Features**:
- Supports multiple action types with specific validation logic for each
- Uses smart image resizing for coordinate normalization
- Implements robust text similarity scoring with configurable threshold
- Handles both coordinate-based and action-based predictions

**Use Case**: End-to-end accuracy evaluation for GUI automation agents performing various interaction tasks.