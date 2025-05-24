import argparse
from api import ApiProcessor_deepseek
import json
import logging
from utils import evaluate_response, Logger, my_evaluate_response, parse_response_to_dict
import os

def main():
    parser = argparse.ArgumentParser(description="Process prompts using an API with object-oriented design.")
    parser.add_argument(
        "--api-token",
        type=str,
        default='sk-0238967eaa304084a7f85c201ab994aa',  # Replace with your actual token or load from env/config
        help="API token",
    )
    parser.add_argument(
        "--base-url", type=str, default="https://api.deepseek.com/v1/chat/completions", help="API base URL"
        # Replace with your actual base URL
    )
    parser.add_argument("--input_file", type=str, default='data/tc_200_zh.json', help="Input JSON file path")
    parser.add_argument("--output_file", type=str, default='task1/tc_200_zh_output_deepseek.json', help="Output JSON file path")
    parser.add_argument(
        "--model", type=str, default="deepseek-chat", help="Model name to use"
    )  # Replace with your actual model
    parser.add_argument("--language", type=str, default="zh", help="language to use")
    args = parser.parse_args()

#==========================================file read============================================================
    if args.language == "zh":
        args.input_file = "data/tc_200_zh.json"
        args.output_file = "task2/tc_200_zh_output_deepseek"
    else:
        args.input_file = "data/tc_200_en.json"
        args.output_file = "task2/tc_200_en_output_deepseek"

    with open(args.input_file, 'r', encoding='utf-8') as f:
        test_data = json.load(f)

    prompts_zh = ["你是伦敦警局首席侦探夏洛克・福尔摩斯，正在调查都铎庄园谋杀案。请根据以下线索推理真相",
               "你正在阅读一部悬疑小说，情节围绕都铎庄园谋杀案展开。请以小说读者的视角分析以下章节内容，推理凶手及作案细节",
               "请分阶段解决这个逻辑谜题：1：提取所有关键线索（如人物、凶器、地点、动机），用列表形式呈现；阶段 2：分析每条线索的约束条件（如‘博迪先生所在房间位于扳手东侧’限定空间关系）；阶段 3：通过排除法缩小嫌疑人 / 物品范围；阶段 4：综合所有条件得出结论。最终答案格式：A. 答案\nB. 答案..."
               ]

    prompts_en = ["You are Sherlock Holmes, the chief detective of the London Police Department, investigating the murder case at Tudor Manor. Please reason out the truth based on the following clues.",
               "You are reading a suspense novel whose plot revolves around the murder case at Tudor Manor. Please analyze the content of the following chapter from the perspective of a novel reader and deduce the murderer and the details of the crime.",
               "Please solve this logic puzzle in stages: Stage 1: Extract all key clues (such as characters, murder weapons, locations, motives), and present them in list form; Stage 2: Analyze the constraints of each clue (such as Mr. Boddy's room is located on the east side of the wrench which limits the spatial relationship); Stage 3: Narrow down the scope of suspects/items through the process of elimination; Stage 4: Synthesize all conditions to draw a conclusion. Final answer format: A. Answer\nB. Answer..."
               ]
    if args.language == "en":
        prompts = prompts_en
    else:
        prompts = prompts_zh

    for idx, prompt in enumerate(prompts):
        output_file = f"{args.output_file}_{idx}.json"
        if os.path.exists(output_file):
            if os.path.getsize(output_file) == 0:
                # 文件为空，初始化空JSON
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump({"results": []}, f)
                print(f"初始化空文件 {output_file}")
        else:
        # 文件不存在，创建并初始化
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump({"results": []}, f)
            print(f"创建新文件 {output_file}")

        with open(output_file, 'r+', encoding='utf-8') as f:
            test_answer = json.load(f)

#=================================main===========================================================
        processor = ApiProcessor_deepseek(
            api_token=args.api_token,
            base_url=args.base_url,
            model=args.model,
            data=test_data
        )

        logger = Logger().get_logger()
        results = []
        if test_answer:
            results += test_answer['results']
        for idx, data in enumerate(test_data):
            if idx >= len(test_answer['results']):
                response = processor.generate_response_with_additional_prompt(args.language, data['prompt'], prompt)
                response = parse_response_to_dict(response)
                print(f'current question:{idx},response:{response}')
                result = {
                    "prompt": data['prompt'],
                    "response": response,
                    "solution":data['solution']
                }
                results.append(result)
                try:
                    with open(output_file, 'w', encoding='utf-8') as f:
                        final_output = {"results": results}
                        json.dump(final_output, f, ensure_ascii=False, indent=2)
                    logging.info(f"Successfully wrote results to {output_file}")
                except IOError as e:
                    logging.error(f"Failed to write output file {output_file}: {e}")
            #else:
                #print("已回答")

    #===================================================evaluate=========================================
        with open(output_file, 'r+', encoding='utf-8') as f:
            answers = json.load(f)
        total_score1 = 0
        total_score2 = 0
        for data in answers['results']:
            score1 = evaluate_response(data['response'], data['solution'])
            score2 = my_evaluate_response(data['response'], data['solution'])['accuracy']
            total_score1 += score1
            total_score2 += score2
        accuracy1 = total_score1 / len(answers['results'])
        accuracy2 = total_score2 / len(answers['results'])
        print(f'total_score1:{total_score1:2f},accuracy: {accuracy1:2f}')
        print(f'total_score2:{total_score2:2f},accuracy: {accuracy2:2f}')

if __name__ == "__main__":
    main()