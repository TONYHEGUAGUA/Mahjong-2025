import requests
import json
from utils import str_to_dict_regex

class ApiProcessor_deepseek:
    def __init__(self, api_token: str, base_url: str, model: str, data):
        if not api_token:
            raise ValueError("API token is required")
        self.api_token = api_token
        self.base_url = base_url
        self.model = model
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_token}"
        }
        self.data = data

    def generate_response(self, language, prompt):
        if language == "en":
            prompt_language = "Please provide the answer directly based on the following content without any inference or additional information. I only need the fixed format answer. Just tell me like A. answer ,followed with a Carriage Return symbol, B. answer ……"
        else:
            prompt_language = "请根据以下内容，不要推理，直接根据要求给出答案，不需要任何其他信息，严格按照A. 答案,B. 答案 ……这样的形式回答我，其中每个答案之间用换行符号分割开, "
        data = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt_language},
                {"role": "user", "content": prompt}
            ]
        }
        try:
            response = requests.post(self.base_url, headers=self.headers, data=json.dumps(data))
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except requests.exceptions.RequestException as e:
            print(f"请求出错: {e}")
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            print(f"解析响应出错: {e}")
        return None

    def generate_response_with_additional_prompt(self, language, additional_prompt, prompt):
        if language == "en":
            prompt_language = "Please provide the answer directly based on the following content without any inference or additional information.I only need the fixed format answer. Just tell me like A. answer ,followed with a Carriage Return symbol, B. answer ……be careful that between A. and answer there is a space"
            prompt_final = "Just give me the answer.A. answer \n B. answer……no other things like inference"
        else:
            prompt_language = "请根据以下内容，不要推理，直接根据要求给出答案，不需要任何其他信息,严格按照以下A. 答案,B. 答案 ……这样的形式回答我, 其中每个答案之间用换行符号分割开,A. 答案之间记得有个空格"
            prompt_final = "我只要结果。A. 答案 \n B.答案 ……"
        data = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": additional_prompt},
                {"role": "user", "content": prompt_language},
                {"role": "user", "content": prompt},
                {"role": "user", "content": prompt_final}
            ]
        }
        try:
            response = requests.post(self.base_url, headers=self.headers, data=json.dumps(data))
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except requests.exceptions.RequestException as e:
            print(f"请求出错: {e}")
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            print(f"解析响应出错: {e}")
        return None

    def clues_get(self, language, prompt, clue_path):
        if language == "en":
            prompt_language = f'''You are a logic puzzle analyst. Please analyze the following puzzle according to Temporal Clue's five-element logic (killer, weapon, room, motive, clues):
                            {prompt}

                            Please return structured information in the following format:
                            {{
                                "entities": {{
                                    "suspects": ["suspect1", "suspect2"],  // All suspects
                                    "weapons": ["weapon1", "weapon2"],    // All weapons
                                    "rooms": ["room1", "room2"],          // Possible crime rooms
                                    "motives": ["motive1", "motive2"]      // All motives
                                }},
                                "raw_clues": ["clue1", "clue2", "clue3"],  // All clue texts extracted from the puzzle
                                "answer": {{
                                    "killer": "killer",        // Extracted from the puzzle's solution (if available)
                                    "weapon": "weapon",        // Leave blank if no solution
                                    "location": "room",
                                    "motive": "motive"
                                }}
                            }}
                            '''
        else:
            prompt_language = f'''你是一位逻辑谜题分析师，请根据Temporal Clue的五元组逻辑（凶手、凶器、房间、动机、线索）分析以下谜题：
                            {prompt}，
                            请按以下格式返回结构化信息：
                            {{
                                "entities": {{
                                    "suspects": ["嫌疑人1", "嫌疑人2"],  // 所有嫌疑人
                                    "weapons": ["凶器1", "凶器2"],    // 所有凶器
                                    "rooms": ["房间1", "房间2"],        // 案发可能房间
                                    "motives": ["动机1", "动机2"]       // 所有动机
                                }},
                                "raw_clues": ["线索1", "线索2", "线索3"],  // 从谜题中提取的所有线索文本
                                "answer": {{
                                    "killer": "凶手",        // 从谜题答案中提取（若有）
                                    "weapon": "凶器",        // 若无答案，留空
                                    "location": "房间",
                                    "motive": "动机"
                                }}
                            }}
                            '''
        data = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt_language}
            ]
        }
        try:
            response = requests.post(self.base_url, headers=self.headers, data=json.dumps(data))
            response.raise_for_status()
            result = response.json()
            llm_response = str_to_dict_regex(result["choices"][0]["message"]["content"])
            print(llm_response)
            formatted_result = {
                "prompt": prompt,  # 原始谜题
                "clues": llm_response # LLM生成的线索
            }
            if clue_path:
                self._save_to_json(formatted_result, clue_path)
        except requests.exceptions.RequestException as e:
            print(f"请求出错: {e}")
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            print(f"解析响应出错: {e}")
        return None

    def _save_to_json(self, data, file_path):
        """将数据追加到JSON文件中，保持列表格式"""
        try:
            # 尝试读取现有文件内容
            with open(file_path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # 文件不存在或为空时，创建新列表
            existing_data = []

        # 追加新数据
        existing_data.append(data)

        # 写回文件
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)

    def ask_to_correct(self, state, language):
        prompt = state['prompt']
        response = state['response']
        solution = state['solution']
        right = []
        wrong = []
        for key in solution.keys():
            if key in response.keys():
                if response[key] == solution[key]:
                    right.append(f'{key}: {response[key]}')
                else:
                    wrong.append(f'{key}: {response[key]}')
            else:
                wrong.append(f'{key}: {response[key]}')

        if language == "en":
            prompt_language = f'The answer you give is partly correct. {right} is correct. {wrong} is wrong.'
            prompt_final = "Just give me the answer.A. answer \n B. answer……no other things like inference"
        else:
            prompt_language = f'你给出的答案中，正确的有{right},错误的有{wrong}，请重新作答'
            prompt_final = "我再说一遍，不要任何其他内容，只要按照如下格式回答我。A. 答案 \n B.答案 ……"
        data = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt_language},
                {"role": "user", "content": prompt},
                {"role": "user", "content": prompt_final}
            ]
        }
        try:
            response = requests.post(self.base_url, headers=self.headers, data=json.dumps(data))
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except requests.exceptions.RequestException as e:
            print(f"请求出错: {e}")
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            print(f"解析响应出错: {e}")
        return None











