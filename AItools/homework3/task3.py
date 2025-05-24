import argparse
from api import ApiProcessor_deepseek
import json
import os
from constraint import Problem
from utils import *

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
    parser.add_argument("--output_file", type=str, default='task3/tc_200_zh_output_deepseek.json', help="Output JSON file path")
    parser.add_argument(
        "--model", type=str, default="deepseek-chat", help="Model name to use"
    )  # Replace with your actual model
    parser.add_argument("--language", type=str, default="zh", help="language to use")
    parser.add_argument("--clues_path", type=str, default='task3/clues.json', help="Clues JSON file path")
    args = parser.parse_args()

#==========================================file read============================================================
    if args.language == "zh":
        args.input_file = "data/tc_200_zh.json"
        args.output_file = "task3/tc_200_zh_output_deepseek"
        args.clues_path = "task3/clues_zh.json"
    else:
        args.input_file = "data/tc_200_en.json"
        args.output_file = "task3/tc_200_en_output_deepseek"
        args.clues_path = "task3/clues_en.json"

    with open(args.input_file, 'r', encoding='utf-8') as f:
        test_data = json.load(f)

    output_file = f"{args.output_file}.json"
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

    if os.path.exists(args.clues_path):
        if os.path.getsize(args.clues_path) == 0:
            # 文件为空，初始化空JSON
            with open(args.clues_path, 'w', encoding='utf-8') as f:
                json.dump([], f)
            print(f"初始化空文件 {args.clues_path}")
    else:
    # 文件不存在，创建并初始化
        with open(args.clues_path, 'w', encoding='utf-8') as f:
            json.dump([], f)
        print(f"创建新文件 {args.clues_path}")

    with open(output_file, 'r+', encoding='utf-8') as f:
        test_answer = json.load(f)

    with open(args.clues_path, 'r', encoding='utf-8') as f:
        clues = json.load(f)

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
    for idx, data in enumerate(test_data):
        if idx >= len(clues):
            #print(f'question:{idx}')
            processor.clues_get(args.language, data['prompt'], args.clues_path)
        #else:
            #print("整理线索完成")

    for idx, data in enumerate(clues):
        if idx >= len(test_answer['results']) and data:
            #print(f'question:{idx}')
            suspects = data['clues']['suspects'] if 'suspects' in data['clues'].keys() else []
            weapons = data['clues']['weapons'] if 'weapons' in data['clues'].keys() else []
            rooms = data['clues']['rooms'] if 'rooms' in data['clues'].keys() else []
            motives = data['clues']['motives'] if 'motives' in data['clues'].keys() else []

            problem = Problem()
            variables = {}

            variables["killer"] = suspects
            variables["weapon"] = weapons
            variables["room"] = rooms
            if motives:
                variables["motive"] = motives

            for var_name, values in variables.items():
                if values:
                    problem.addVariable(var_name, values)

            for clue in clues:
                if "凶器" in clue or "武器" in clue or "来自" in clue:
                    for weapon in weapons:
                        if weapon.lower() in clue:
                            problem.addConstraint(lambda w=weapon: w == weapon, "weapon")

                if "在...的" in clue and ("南" in clue or "北" in clue or "东" in clue or "西" in clue):
                    parts = clue.split("在")
                    if len(parts) >= 2:
                        entity = parts[0].strip()
                        location_part = parts[1].split("的")[0].strip()
                        direction = parts[1].split("的")[-1].strip()

                        room_layout = {room.lower(): direction for room, direction in zip(rooms, ["北", "南"])}  # 示例布局
                        if entity in suspects + weapons:
                            if location_part in room_layout:
                                problem.addConstraint(lambda r=location_part: r == location_part, "room")

                if "动机" in clue and any(suspect.lower() in clue for suspect in suspects):
                    for suspect in suspects:
                        if suspect.lower() in clue:
                            for motive in motives:
                                if motive.lower() in clue:
                                    problem.addConstraint(lambda m=motive: m == motive, "motive")

                if "或" in clue and "在" in clue:
                    parts = clue.split("或")
                    entities_in_room = [p.strip().split("在")[0] for p in parts if "在" in p]
                    room_name = clue.split("在")[-1].strip()
                    problem.addConstraint(
                        lambda *args: any(entity == room_name for entity in args),
                        [f"{entity}_location" for entity in entities_in_room]
                    )

            solutions = problem.getSolutions()
            #print(solutions[0] if solutions else None)
            problems = extract_questions_by_line(test_data[idx]['prompt'])
            #print(problems)
            response = {}
            for key, value in problems.items():
                if solutions:
                    if "凶手" in value or "谁" in value or "真凶" in value:
                        response[key]=solutions[0]['killer'] if "killer" in solutions[0].keys() else []
                    if "凶器" in value:
                        response[key]=solutions[0]['weapon'] if "weapon" in solutions[0].keys() else []
                    if "动机" in value:
                        response[key]=solutions[0]['motive'] if "motive" in solutions[0].keys() else []
                    if "命案" in value or "凶案" in value or "案发" in value:
                        response[key]=solutions[0]['room'] if "room" in solutions[0].keys() else []
                else:
                    response[key] = []
            #print(response)
            result = {
                "prompt": test_data[idx]['prompt'],
                "response": response,
                "solution":test_data[idx]['solution']
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