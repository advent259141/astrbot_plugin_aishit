from astrbot.api.all import *
import re
import aiohttp
import json
import os
from pathlib import Path
from astrbot.api.event import filter, AstrMessageEvent

@register("aishit", "Jason.Joestar", "一个AI生成搞笑聊天记录的插件", "1.0.0", "插件仓库URL")
class AiShitPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        logger.debug("AI造屎插件已初始化")
    
    async def get_qq_nickname(self, qq_number):
        """获取QQ昵称"""
        url = f"http://api.mmp.cc/api/qqname?qq={qq_number}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    try:
                        data = await response.json()
                        logger.debug(f"QQ昵称API返回: {data}")
                        
                        if data.get("code") == 200 and "data" in data and "name" in data["data"]:
                            nickname = data["data"]["name"]
                            logger.debug(f"成功提取昵称: {nickname}")
                            if nickname:
                                return nickname
                    except Exception as e:
                        logger.debug(f"解析昵称出错: {str(e)}")
        
        return f"用户{qq_number}"
    
    async def generate_shit_chat(self):
        """
        调用LLM生成搞笑/猎奇的聊天记录
        
        Returns:
            str: 生成的聊天记录字符串
        """
        # 获取LLM工具管理器
        func_tools_mgr = self.context.get_llm_tool_manager()
        
        # 构建系统提示词
        system_prompt = """你是一个专业造屎专家，致力于通过聊天记录构造，来描写一些搞笑或者猎奇的事。
你需要输出的聊天记录的格式为严格的：
用户ID 用户说的话 | 用户ID 用户说的话 | 用户ID 用户说的话 | ...
其中用户ID是QQ号，是一串数字。每个发言之间用 | 符号分隔。
不要输出任何其他内容，只输出聊天记录。不要加任何解释。"""
        
        # 构建用户提示词
        prompt = """请严格依据格式要求，生成一段搞笑/猎奇/让人无语的屎聊天记录，要贴合生活实际以及网络上的热梗。
每个发言的格式是"QQ号 消息内容"，不同发言之间用"|"分隔。
QQ号应该是7-10位的数字。
请确保生成的聊天记录有故事性和趣味性，能引起读者的兴趣，而且要形成一件完整的事件或者故事。
请直接输出格式正确的聊天记录，不要有任何其他说明性文字。"""
        
        # 调用LLM
        llm_response = await self.context.get_using_provider().text_chat(
            prompt=prompt,
            session_id=None,
            contexts=[],
            image_urls=[],
            func_tool=func_tools_mgr,
            system_prompt=system_prompt
        )
        
        # 获取生成的文本
        if llm_response.role == "assistant":
            generated_text = llm_response.completion_text.strip()
            logger.debug(f"LLM生成的聊天记录: {generated_text}")
            return generated_text
        else:
            logger.error(f"LLM生成失败，角色: {llm_response.role}")
            return "生成失败，请重试"

    def parse_shit_chat(self, chat_text):
        """
        解析生成的聊天记录，返回可以用于伪造消息的格式
        
        Args:
            chat_text: LLM生成的聊天记录文本
            
        Returns:
            list: 解析后的聊天段落列表
        """
        # 清理文本，确保格式正确
        chat_text = chat_text.strip()
        
        # 按"|"分割聊天记录
        segments = [seg.strip() for seg in chat_text.split('|')]
        
        parsed_segments = []
        for segment in segments:
            if not segment:
                continue
                
            # 尝试分离QQ号和消息内容
            parts = segment.strip().split(' ', 1)
            if len(parts) == 2:
                qq_number, content = parts
                # 确保QQ号是数字
                if qq_number.isdigit():
                    parsed_segments.append({
                        "text": segment.strip(),
                        "images": []
                    })
        
        logger.debug(f"解析后的段落数: {len(parsed_segments)}")
        return parsed_segments
    
    @filter.command("ai造屎")
    async def ai_shit(self, event: AstrMessageEvent):
        """生成搞笑/猎奇的伪造聊天记录"""
        from astrbot.api.message_components import Node, Plain, Nodes
        
        try:
            # 先告知用户正在生成
            yield event.plain_result("正在生成新鲜的屎，请稍候...")
            
            # 调用LLM生成聊天记录
            chat_text = await self.generate_shit_chat()
            
            # 解析生成的聊天记录
            segments = self.parse_shit_chat(chat_text)
            
            # 如果没有成功解析任何段落，返回错误消息
            if not segments:
                yield event.plain_result("生成的聊天记录格式有误，请重试")
                return
            
            # 构建节点列表
            nodes_list = []
            
            for segment in segments:
                text = segment["text"]
                
                match = re.match(r'^\s*(\d+)\s+(.*)', text)
                if not match:
                    logger.debug(f"段落格式错误，跳过: {text}")
                    continue
                    
                qq_number, content = match.group(1), match.group(2).strip()
                
                nickname = await self.get_qq_nickname(qq_number)
                
                node_content = [Plain(content)]
                
                node = Node(
                    uin=int(qq_number),
                    name=nickname,
                    content=node_content
                )
                nodes_list.append(node)
            
            if nodes_list:
                nodes = Nodes(nodes=nodes_list)
                yield event.chain_result([nodes])
            else:
                yield event.plain_result("未能解析出任何有效的消息节点")
                
        except Exception as e:
            logger.error(f"AI造屎功能出错: {str(e)}")
            yield event.plain_result(f"生成失败: {str(e)}")
            
    async def terminate(self):
        '''插件被卸载/停用时调用'''
        pass
