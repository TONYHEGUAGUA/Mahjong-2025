#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @Time    : 2020/2/25 15:45
# @Author  : Vodka0629
# @Email   : 563511@qq.com, ZhangXiangming@gmail.com
# @FileName: player_human.py
# @Software: Mahjong II
# @Blog    :

import sys
import pygame
import requests
import json
import os
import asyncio
import aiohttp
import threading
from typing import Dict, List, Any
from concurrent.futures import ThreadPoolExecutor

from mahjong.mj_math import MjMath
from mahjong.mj_set import MjSet
from mahjong.player import Player
from mahjong.rule import Rule
from mahjong.tile import Tile
from mahjong.suit import Suit
from setting import Setting


class PlayerHuman(Player):
    __slots__ = ('cmd', 'hand', 'waiting_group', 'waiting_cmd', 'api_processor', 'last_hand_state', 'cached_ai_suggestion', 'executor')

    def __init__(self, nick="Eric", coin: int = 0,
                 is_viewer: bool = False, viewer_position: str = '东',
                 screen=None, clock=None):
        super().__init__(nick=nick, coin=coin,
                         is_viewer=is_viewer, viewer_position=viewer_position,
                         screen=screen, clock=clock)
        self.cmd = ''
        self.waiting_cmd = []
        self.waiting_group = pygame.sprite.Group()
        self.last_hand_state = None
        self.cached_ai_suggestion = None
        self.executor = ThreadPoolExecutor(max_workers=1)
        
        # Initialize API processor with default token
        api_token = os.getenv('DEEPSEEK_API_KEY', 'sk-0238967eaa304084a7f85c201ab994aa')
        self.api_processor = None
        try:
            self.api_processor = DeepseekMahjongAI(
                api_token=api_token,
                base_url="https://api.deepseek.com/v1/chat/completions",
                model="deepseek-chat"
            )
        except Exception as e:
            print(f"Warning: Failed to initialize AI processor: {e}")
            self.api_processor = None

    def draw(self, mj_set: MjSet):
        return super().draw(mj_set)

    def decide_discard(self) -> Tile:
        self.current_index = len(self._concealed) - 1
        choices = [[index] for index, tile in enumerate(self._concealed)]
        self.current_tiles = choices[self.current_index]
        if self.hand:
            self.hand.refresh_screen()
        allowed_cmd = ['discard']
        self.waiting_4_cmd(allowed_cmd=allowed_cmd, choices=choices, allow_sort=True)
        tile = self._concealed[self.current_index]
        self.current_tiles = []
        # self.sort_concealed()
        return tile

    def draw_waiting_cmd(self):
        self.waiting_group.empty()
        if not self.waiting_cmd:
            return
        left = Setting.concealed_bottom
        bottom = Setting.win_h - Setting.concealed_bottom
        for cmd in self.waiting_cmd:
            if cmd not in Setting.waiting_img:
                continue
            cmd_img = Setting.sprite_base + Setting.waiting_img[cmd]
            image = pygame.image.load(cmd_img)
            rect = image.get_rect()
            rect.left = left
            rect.bottom = bottom
            sprite = pygame.sprite.Sprite()
            sprite.image = image
            sprite.rect = rect
            self.waiting_group.add(sprite)
            left += rect.w + Setting.waiting_img_span

    def draw_screen(self, state: str = ''):
        super().draw_screen(state=state)
        if self.screen:
            self.draw_waiting_cmd()
            self.waiting_group.draw(self.screen)

    def try_mahjong(self, tile=None) -> bool:
        test = self.concealed[:]
        if tile:
            test.append(tile)
        if Rule.is_mahjong(test):
            choices = []
            allowed_cmd = ['hu', 'cancel']
            cmd = self.waiting_4_cmd(allowed_cmd=allowed_cmd, choices=choices)
            if cmd == 'cancel':
                return False
            elif cmd == 'hu':
                return True
            else:
                raise ValueError("exposed pong error cmd:", cmd)

        return False

    def try_exposed_pong(self, tile: Tile, owner) -> bool:
        count = 0
        arr = []
        for index, test in enumerate(self._concealed):
            if tile.key == test.key:
                count += 1
                arr.append(index)
                if count >= 2:
                    break
        if count < 2:
            # no chance for pong
            return False

        choices = [arr]
        allowed_cmd = ['pong', 'cancel']
        cmd = self.waiting_4_cmd(allowed_cmd=allowed_cmd, choices=choices)
        if cmd == 'cancel':
            return False
        elif cmd == 'pong':
            self.exposed_pong(tile, owner=owner)
            return True
        else:
            raise ValueError("exposed pong error cmd:", cmd)

    def try_conceal_kong(self, mj_set: MjSet) -> bool:
        if not self.concealed:
            return False
        if not mj_set.tiles:
            return False
        test_tiles = list(set(self.concealed))
        choices = []
        for x in test_tiles:
            choice = []
            if self.concealed.count(x) < 4:
                continue
            count = 0
            for index, y in enumerate(self.concealed):
                if x.key == y.key:
                    choice.append(index)
                    count += 1
                    if count >= 4:
                        break
            choices.append(choice)

        if not choices:
            return False

        allowed_cmd = ['kong', 'cancel']
        self.current_index = 0
        cmd = self.waiting_4_cmd(allowed_cmd=allowed_cmd, choices=choices)
        if cmd == 'cancel':
            return False
        elif cmd == 'kong':
            print("self.current_index:", self.current_index)
            print("choices:", choices)
            tile_index = choices[self.current_index][0]
            tile = self.concealed[tile_index]
            self.concealed_kong(tile=tile, mj_set=mj_set)
            return True
        else:
            raise ValueError("concealed kong error cmd:", cmd)

    def try_exposed_kong_from_exposed_pong(self, mj_set: MjSet) -> bool:
        tile = self.concealed[-1]
        if not mj_set.tiles:
            return False
        if not self.exposed:
            return False
        for expose in self.exposed:
            if expose.expose_type == 'exposed pong' and expose.outer.key == tile.key:
                print("human player's try_exposed_kong_from_exposed_pong")
                print("tile:", tile)
                print("expose:", expose)
                allowed_cmd = ['kong', 'cancel']
                self.current_index = 0
                choices = [[len(self.concealed) - 1]]
                cmd = self.waiting_4_cmd(allowed_cmd=allowed_cmd, choices=choices)
                if cmd == 'cancel':
                    return False
                elif cmd == 'kong':
                    self.exposed_kong_from_exposed_pong(tile=tile, expose=expose, mj_set=mj_set)
                    return True
        return False

    def try_exposed_kong(self, tile: Tile, owner, mj_set: MjSet) -> bool:
        count = 0
        arr = []
        for index, test in enumerate(self._concealed):
            if tile.key == test.key:
                count += 1
                arr.append(index)
                if count >= 3:
                    break
        if count < 3:
            # no chance for kong
            return False

        choices = [arr]
        allowed_cmd = ['kong', 'cancel']
        cmd = self.waiting_4_cmd(allowed_cmd=allowed_cmd, choices=choices)
        if cmd == 'cancel':
            return False
        elif cmd == 'kong':
            self.exposed_kong(tile, owner=owner, mj_set=mj_set)
            return True
        else:
            raise ValueError("exposed kong error cmd:", cmd)

    def try_exposed_chow(self, tile: Tile, owner) -> bool:
        arr = Rule.convert_tiles_to_arr(self.concealed)
        outer = tile.key

        combins = MjMath.get_chow_combins_from_arr(arr=arr, outer=outer)
        if not combins:
            return False

        # convert combins to index arrays
        choices = []
        for combin in combins:
            choice = []
            for x in combin:
                index = arr.index(x)
                choice.append(index)
            choices.append(choice)

        allowed_cmd = ['chow', 'cancel']
        cmd = self.waiting_4_cmd(allowed_cmd=allowed_cmd, choices=choices)
        if cmd == 'cancel':
            return False
        elif cmd == 'chow':
            arr = choices[self.current_index]
            inners = []
            for index in arr:
                inners.append(self._concealed[index])
            super().exposed_chow(inners=inners, tile=tile, owner=owner)
            return True
        else:
            raise ValueError("exposed chow error cmd:", cmd)
    #每次轮到用户抉择的时候会调用
    def waiting_4_cmd(self, allowed_cmd=[], choices=[], allow_sort=False, draw_screen=True):
        # 使用新的方法打印游戏状态
        self.print_game_state()
        
        # 打印当前可用命令
        cmd_descriptions = {
            'chow': '吃',
            'pong': '碰',
            'kong': '杠',
            'hu': '胡',
            'cancel': '取消',
            'discard': '打出',
            'draw': '摸牌'
        }
        
        print("\n当前可用命令:")
        cmd_text = []
        for cmd in allowed_cmd:
            if cmd in cmd_descriptions:
                if cmd == 'discard' and choices:
                    cmd_text.append("左右键切换牌/Enter键打出")
                else:
                    key = {'chow': 'C', 'pong': 'P', 'kong': 'K', 'hu': 'H', 'cancel': 'ESC', 'draw': 'Space'}
                    if cmd in key:
                        cmd_text.append(f"{cmd_descriptions[cmd]}({key[cmd]})")
                    else:
                        cmd_text.append(cmd_descriptions[cmd])
        print(" ".join(cmd_text))
        print()  # 空行分隔

        key_left_lasttime = 0
        key_right_lasttime = 0
        if not allowed_cmd:
            raise ValueError("need at least one allowed_cmd:", allowed_cmd)
        default_cmd = allowed_cmd[0]

        if choices:
            if self.current_index < 0 or (len(choices) - 1) < self.current_index:
                self.current_index = 0
            self.current_tiles = choices[self.current_index]

        # refresh the screen
        self.waiting_cmd = allowed_cmd
        # self.waiting_cmd = ['hu', 'cancel']  # test for cmd buttons
        if draw_screen:
            self.draw_screen()
            if self.hand:
                self.hand.refresh_screen()

        cmd = ''
        step = 0
        while not cmd or cmd not in allowed_cmd:
            step += 1
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    # 判断当前事件是否为点击右上角退出键
                    pygame.quit()
                    sys.exit()

            # 使用键盘提供的方法获取键盘按键 - 按键元组
            keys_pressed = pygame.key.get_pressed()

            changed = False
            if keys_pressed[pygame.K_s]:
                changed = True
                self.sort_concealed()
            if keys_pressed[pygame.K_c]:
                changed = True
                cmd = "chow"
            if keys_pressed[pygame.K_p]:
                changed = True
                cmd = "pong"
            if keys_pressed[pygame.K_k]:
                changed = True
                cmd = "kong"
            if keys_pressed[pygame.K_h]:
                changed = True
                cmd = "hu"
            if keys_pressed[pygame.K_SPACE]:
                changed = True
                cmd = "draw"
            if keys_pressed[pygame.K_ESCAPE]:
                changed = True
                cmd = "cancel"
            if keys_pressed[pygame.K_RETURN] or keys_pressed[pygame.K_KP_ENTER]:
                changed = True
                cmd = default_cmd
            if keys_pressed[pygame.K_LEFT]:
                current_time = pygame.time.get_ticks()
                if choices and (current_time - key_left_lasttime)>300:
                    key_left_lasttime = current_time
                    changed = True
                    self.current_index -= 1
                    if self.current_index < 0:
                        self.current_index = len(choices) - 1
                    self.current_tiles = choices[self.current_index]
            if keys_pressed[pygame.K_RIGHT]:
                current_time = pygame.time.get_ticks()
                if choices and (current_time - key_right_lasttime)>300:
                    key_right_lasttime = current_time
                    changed = True
                    self.current_index += 1
                    if self.current_index >= len(choices):
                        self.current_index = 0
                    self.current_tiles = choices[self.current_index]
            if cmd not in allowed_cmd:
                cmd = ''

            self.clock.tick(Setting.cmd_FPS)

            # if self.hand and changed:
            if hasattr(self, 'hand') and changed:
                self.hand.refresh_screen()

        self.waiting_cmd = []
        self.draw_screen()
        # if self.hand:
        if hasattr(self, 'hand'):
            self.hand.refresh_screen()
        pygame.event.clear()  # 新增：清空事件队列
        self.clock.tick(Setting.cmd_FPS)
        return cmd

    def get_game_state_dict(self):
        """获取并返回游戏状态的字典格式"""
        game_state = {
            "自己的手牌": [str(tile) for tile in self.concealed],
            "其他玩家": {}
        }
        
        # 遍历其他玩家
        for player in self.hand._players:
            if player != self:
                # 确定玩家关系
                if player.position == Suit.get_before_wind(self.position):
                    relation = "上家"
                elif player.position == Suit.get_opposition_wind(self.position):
                    relation = "对家"
                elif player.position == Suit.get_next_wind(self.position):
                    relation = "下家"
                else:
                    continue
                
                # 处理该玩家的信息
                player_info = {
                    "明牌": [],
                    "打出的牌": [str(tile) for tile in player.desk]
                }
                
                # 处理明牌
                for expose in player.exposed:
                    expose_str = str(expose)
                    if expose.outer_owner:
                        expose_str = expose_str.replace(expose.outer_owner.nick, relation)
                    player_info["明牌"].append(expose_str)
                
                game_state["其他玩家"][relation] = player_info
        
        return game_state

    def get_ai_suggestion(self, game_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        使用 Deepseek API 获取 AI 建议
        """
        if not self.api_processor:
            return {"error": "No API processor available"}

        return self.api_processor.get_suggestion_sync(game_state)

    def print_ai_suggestion(self, ai_suggestion: Dict[str, Any]):
        """打印AI建议"""
        if not ai_suggestion:
            return
            
        if "error" in ai_suggestion:
            print("\nAI建议获取失败:", ai_suggestion["error"])
            return

        print("\n=== AI 策略建议 ===")
        
        if "actions" in ai_suggestion and ai_suggestion["actions"]:
            print("\n可能的行动建议:")
            for action in ai_suggestion["actions"]:
                print(f"- {action['action']}: 权重 {action['weight']}")
        
        if "discard_suggestions" in ai_suggestion and ai_suggestion["discard_suggestions"]:
            print("\n打牌建议:")
            for suggestion in ai_suggestion["discard_suggestions"]:
                print(f"- {suggestion['tile']}: 权重 {suggestion['weight']}")
        
        if "strategy_analysis" in ai_suggestion and ai_suggestion["strategy_analysis"]:
            print("\n策略分析:")
            print(ai_suggestion.get("strategy_analysis", "无分析"))
        
        print("\n==================")

    def print_game_state(self):
        """打印游戏状态信息"""
        game_state = self.get_game_state_dict()
        
        print("\n当前游戏状态:")
        print("自己的手牌:", game_state["自己的手牌"])
        
        for relation, info in game_state["其他玩家"].items():
            print(f"\n{relation}:")
            print(f"  明牌:", info["明牌"])
            print(f"  打出的牌:", info["打出的牌"])
        print()  # 空行分隔

        # 检查是否需要更新AI建议
        if self.should_update_ai_suggestion():
            print("检测到状态变化，更新AI建议...")  # Debug信息
            self.update_ai_suggestion(game_state)
        elif self.cached_ai_suggestion:
            print("使用缓存的AI建议...")  # Debug信息
            self.print_ai_suggestion(self.cached_ai_suggestion)

    def get_hand_state(self):
        """获取当前手牌状态的哈希值，用于判断手牌是否改变"""
        return (
            tuple(sorted(str(tile) for tile in self.concealed)),
            tuple((str(expose) for expose in self.exposed)),
            tuple((player.nick, tuple(str(tile) for tile in player.desk)) for player in self.hand._players if player != self)
        )

    def should_update_ai_suggestion(self):
        """判断是否需要更新AI建议"""
        current_state = self.get_hand_state()
        if self.last_hand_state != current_state:
            self.last_hand_state = current_state
            return True
        return False

    def sort_concealed(self):
        """重写排序方法，避免触发AI建议更新"""
        old_state = self.get_hand_state()
        super().sort_concealed()
        self.last_hand_state = old_state  # 保持状态不变，因为排序不需要更新AI建议

    def update_ai_suggestion(self, game_state):
        """在新线程中更新AI建议"""
        def get_suggestion_sync():
            try:
                print("开始获取AI建议...")  # Debug信息
                if not self.api_processor:
                    print("API处理器未初始化")  # Debug信息
                    return None
                
                # 添加当前可用命令到游戏状态
                game_state['available_commands'] = self.waiting_cmd
                
                # 使用同步方式获取建议
                suggestion = self.api_processor.get_suggestion_sync(game_state)
                print(f"获取到AI建议: {suggestion}")  # Debug信息
                
                if suggestion:
                    self.cached_ai_suggestion = suggestion
                    self.print_ai_suggestion(suggestion)
                return suggestion
            except Exception as e:
                print(f"获取AI建议时出错: {str(e)}")  # Debug信息
                return None

        # 在线程池中执行
        self.executor.submit(get_suggestion_sync)


class DeepseekMahjongAI:
    def __init__(self, api_token: str, base_url: str, model: str):
        if not api_token:
            raise ValueError("API token is required")
        self.api_token = api_token
        self.base_url = base_url
        self.model = model
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_token}"
        }
        # 设置重试次数和超时
        self.max_retries = 3
        self.timeout = 30

    def get_suggestion_sync(self, game_state: Dict[str, Any]) -> Dict[str, Any]:
        """同步获取AI建议"""
        try:
            import requests
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            
            # 创建带重试机制的session
            session = requests.Session()
            retry_strategy = Retry(
                total=self.max_retries,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("https://", adapter)
            
            prompt = self._create_prompt(game_state)
            data = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 800
            }
            
            print(f"发送API请求到 {self.base_url}...")  # Debug信息
            response = session.post(
                self.base_url,
                headers=self.headers,
                json=data,
                timeout=(5, self.timeout)  # (连接超时, 读取超时)
            )
            response.raise_for_status()
            result = response.json()
            
            content = result["choices"][0]["message"]["content"]
            print(f"成功收到API响应")  # Debug信息
            
            # 解析返回的格式化文本
            return self._parse_response(content)
            
        except requests.exceptions.ConnectTimeout:
            print("连接超时，请检查网络连接")
            return {"error": "Connection timeout, please check your network"}
        except requests.exceptions.ReadTimeout:
            print("读取超时，服务器响应时间过长")
            return {"error": "Read timeout, server response took too long"}
        except requests.exceptions.ConnectionError:
            print("连接错误，请检查网络连接或API地址是否正确")
            return {"error": "Connection error, please check your network or API endpoint"}
        except Exception as e:
            print(f"API请求出错: {str(e)}")
            return {"error": f"API request failed: {str(e)}"}

    def _create_prompt(self, game_state: Dict[str, Any]) -> str:
        """创建提示信息"""
        # 获取当前可用命令
        available_commands = game_state.get('available_commands', [])
        special_commands = {'pong', 'chow', 'kong', 'hu'}
        has_special_command = any(cmd in special_commands for cmd in available_commands)
        
        base_prompt = f"""
当前状态：
我的手牌: {game_state['自己的手牌']}

其他玩家情况：
{json.dumps(game_state['其他玩家'], ensure_ascii=False, indent=2)}

当前可用命令: {', '.join(available_commands)}
"""
        
        # 根据可用命令调整提示语
        if has_special_command:
            prompt_language = """
请根据以下内容，分析是否应该执行当前可用的动作（吃/碰/杠/胡），严格按照以下格式回答：

A. 当前动作建议：
   - 动作: [可用命令中的动作], 权重: [0-100的数字]
   - 动作: 取消, 权重: [0-100的数字]

B. 策略分析：
   [分析是否应该执行当前动作的原因]
"""
        else:
            prompt_language = """
请分析当前局势，建议应该打出哪些牌，严格按照以下格式回答：

A. 打牌建议（按权重从高到低排序）：
   - 牌: [牌名], 权重: [0-100的数字]

B. 策略分析：
   [简短的策略分析文本，解释打牌建议的原因]
"""
        return base_prompt + prompt_language

    def _parse_response(self, content: str) -> Dict[str, Any]:
        """解析API响应"""
        try:
            actions = []
            discard_suggestions = []
            strategy_analysis = ""
            
            # 分割AB或ABC部分
            parts = content.split('\n')
            current_section = None
            
            for line in parts:
                line = line.strip()
                if not line:
                    continue
                    
                if line.startswith('A.'):
                    if '打牌建议' in line:
                        current_section = 'discard'
                    else:
                        current_section = 'actions'
                    continue
                elif line.startswith('B.'):
                    if current_section == 'discard':
                        current_section = 'strategy'
                    else:
                        current_section = 'strategy'
                    continue
                    
                if current_section == 'actions' and line.startswith('-'):
                    if '权重:' in line:
                        action = line.split('动作:')[1].split('权重:')[0].strip()
                        weight = int(line.split('权重:')[1].strip())
                        actions.append({"action": action, "weight": weight})
                elif current_section == 'discard' and line.startswith('-'):
                    if '权重:' in line:
                        tile = line.split('牌:')[1].split('权重:')[0].strip()
                        weight = int(line.split('权重:')[1].strip())
                        discard_suggestions.append({"tile": tile, "weight": weight})
                elif current_section == 'strategy':
                    strategy_analysis += line + " "
            
            return {
                "actions": actions,
                "discard_suggestions": discard_suggestions,
                "strategy_analysis": strategy_analysis.strip()
            }
        except Exception as e:
            print(f"解析响应时出错: {str(e)}")  # Debug信息
            print(f"原始响应内容: {content}")  # Debug信息
            return {"error": f"Failed to parse response: {str(e)}"}

    def print_ai_suggestion(self, ai_suggestion: Dict[str, Any]):
        """打印AI建议"""
        if not ai_suggestion:
            return
            
        if "error" in ai_suggestion:
            print("\nAI建议获取失败:", ai_suggestion["error"])
            return

        print("\n=== AI 策略建议 ===")
        
        # 只在有特殊命令时显示行动建议
        if ai_suggestion.get("actions"):
            print("\n当前动作建议:")
            for action in ai_suggestion["actions"]:
                print(f"- {action['action']}: 权重 {action['weight']}")
        
        # 只在普通打牌时显示打牌建议
        if ai_suggestion.get("discard_suggestions"):
            print("\n打牌建议:")
            for suggestion in ai_suggestion["discard_suggestions"]:
                print(f"- {suggestion['tile']}: 权重 {suggestion['weight']}")
        
        if ai_suggestion.get("strategy_analysis"):
            print("\n策略分析:")
            print(ai_suggestion["strategy_analysis"])
        
        print("\n==================")

    def print_game_state(self):
        """打印游戏状态信息"""
        game_state = self.get_game_state_dict()
        
        print("\n当前游戏状态:")
        print("自己的手牌:", game_state["自己的手牌"])
        
        for relation, info in game_state["其他玩家"].items():
            print(f"\n{relation}:")
            print(f"  明牌:", info["明牌"])
            print(f"  打出的牌:", info["打出的牌"])
        print()  # 空行分隔

        # 获取并显示AI建议（如果可用）
        if self.api_processor:
            ai_suggestion = self.api_processor.get_suggestion_sync(game_state)
            self.print_ai_suggestion(ai_suggestion)
