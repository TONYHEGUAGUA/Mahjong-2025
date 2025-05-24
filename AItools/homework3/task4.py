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
    parser.add_argument("--output_file", type=str, default='task4/tc_200_zh_output_deepseek.json', help="Output JSON file path")
    parser.add_argument(
        "--model", type=str, default="deepseek-chat", help="Model name to use"
    )  # Replace with your actual model
    parser.add_argument("--language", type=str, default="en", help="language to use")
    args = parser.parse_args()

#==========================================file read============================================================
    if args.language == "zh":
        args.input_file = "data/tc_200_zh.json"
        args.output_file = "task4/tc_200_zh_output_deepseek"
    else:
        args.input_file = "data/tc_200_en.json"
        args.output_file = "task4/tc_200_en_output_deepseek"

    with open(args.input_file, 'r', encoding='utf-8') as f:
        test_data = json.load(f)

    for idx in range(5):
        output_file = f"{args.output_file}_{idx}.json"
        #print(f'output: {output_file}')
        if os.path.exists(output_file):
            if os.path.getsize(output_file) == 0:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump({"results": []}, f)
                #print(f"初始化空文件 {output_file}")
        else:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump({"results": []}, f)
            #print(f"创建新文件 {output_file}")

        with open(output_file, 'r+', encoding='utf-8') as f:
            test_answer = json.load(f)

        if idx > 0:
            to_correct_file = f'{args.output_file}_{idx-1}.json'
            #print(f'now correcting file: {to_correct_file}')
            with open(to_correct_file, 'r', encoding='utf-8') as f:
                to_correct_data = json.load(f)

#=================================main===========================================================
        processor = ApiProcessor_deepseek(
            api_token=args.api_token,
            base_url=args.base_url,
            model=args.model,
            data=test_data
        )

        results = []
        if test_answer:
            results += test_answer['results']
        if idx == 0:
            for i, data in enumerate(test_data):
                if i >= len(test_answer['results']):
                    response = processor.generate_response(args.language, data['prompt'])
                    response = parse_response_to_dict(response)
                    print(f'current question:{i},response:{response}')
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
        else:
            for i, data in enumerate(to_correct_data['results']):
                if i >= len(test_answer['results']):
                    print(f'round{idx}, question:{i}:')
                    response = processor.ask_to_correct(data, args.language)
                    response = parse_response_to_dict(response)
                    print(f'response:{response}')
                    result = {
                        "prompt": data['prompt'],
                        "response": response,
                        "solution": data['solution']
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
                    #print("已纠正")

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