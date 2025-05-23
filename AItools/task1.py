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
    parser.add_argument("--language", type=str, default="en", help="language to use")
    args = parser.parse_args()

#==========================================file read============================================================
    if args.language == "zh":
        args.input_file = "data/tc_200_zh.json"
        args.output_file = "task1/tc_200_zh_output_deepseek.json"
    else:
        args.input_file = "data/tc_200_en.json"
        args.output_file = "task1/tc_200_en_output_deepseek.json"

    with open(args.input_file, 'r', encoding='utf-8') as f:
        test_data = json.load(f)

    if os.path.exists(args.output_file):
        if os.path.getsize(args.output_file) == 0:
            # 文件为空，初始化空JSON
            with open(args.output_file, 'w', encoding='utf-8') as f:
                json.dump({"results": []}, f)
            print(f"初始化空文件 {args.output_file}")
    else:
        # 文件不存在，创建并初始化
        with open(args.output_file, 'w', encoding='utf-8') as f:
            json.dump({"results": []}, f)
        print(f"创建新文件 {args.output_file}")

    with open(args.output_file, 'r+', encoding='utf-8') as f:
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
            response = processor.generate_response(args.language, data['prompt'])
            response = parse_response_to_dict(response)
            print(f'current question:{idx},response:{response}')
            result = {
                "prompt": data['prompt'],
                "response": response,
                "solution":data['solution']
            }
            results.append(result)
            try:
                with open(args.output_file, 'w', encoding='utf-8') as f:
                    final_output = {"results": results}
                    json.dump(final_output, f, ensure_ascii=False, indent=2)
                logging.info(f"Successfully wrote results to {args.output_file}")
            except IOError as e:
                logging.error(f"Failed to write output file {args.output_file}: {e}")
        #else:
            #print("已回答")

#===================================================evaluate=========================================
    with open(args.output_file, 'r+', encoding='utf-8') as f:
        answers = json.load(f)
    total_score1 = 0
    total_score2 = 0
    for data in answers['results']:
        score1 = evaluate_response(data['response'], data['solution'])
        score2 = my_evaluate_response(data['response'], data['solution'])['accuracy']
        #print(score1, score2)
        total_score1 += score1
        total_score2 += score2
    accuracy1 = total_score1 / len(answers['results'])
    accuracy2 = total_score2 / len(answers['results'])
    print(f'total_score1:{total_score1:2f},accuracy: {accuracy1:2f}')
    print(f'total_score2:{total_score2:2f},accuracy: {accuracy2:2f}')

if __name__ == "__main__":
    main()