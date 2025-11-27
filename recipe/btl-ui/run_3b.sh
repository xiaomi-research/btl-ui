MODEL_PATH=Qwen/Qwen2.5-VL-3B-Instruct
SAVE_PATH=ckpt/BTL-UI-3B
DATASET_PATH=""


CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 \
MAX_PIXELS=4014080 \
NPROC_PER_NODE=8 \
swift rlhf \
    --rlhf_type grpo \
    --model_type qwen2_5_vl \
    --model $MODEL_PATH \
    --external_plugins recipe/btl-ui/reward_fn.py \
    --reward_funcs external_gui_agent_format_reward external_gui_agent_blink_reward external_gui_agent_accuracy_reward \
    --reward_weights 0.1 0.3 0.6 \
    --use_vllm true \
    --vllm_gpu_memory_utilization 0.6 \
    --vllm_max_model_len 8192 \
    --freeze_vit false \
    --train_type full \
    --torch_dtype bfloat16 \
    --dataset $DATASET_PATH \
    --max_completion_length 1280 \
    --num_train_epochs 3 \
    --per_device_train_batch_size 1 \
    --per_device_eval_batch_size 1 \
    --learning_rate 1e-6 \
    --gradient_accumulation_steps 2 \
    --eval_strategy 'no' \
    --eval_steps 200 \
    --save_steps 200 \
    --save_total_limit 2 \
    --logging_steps 1 \
    --max_length 4096 \
    --output_dir $SAVE_PATH \
    --warmup_ratio 0.05 \
    --dataloader_num_workers 4 \
    --dataset_num_proc 4 \
    --num_generations 8 \
    --temperature 0.9 \
    --system 'You are a GUI Agent.' \
    --deepspeed zero3 \
    --log_completions true
