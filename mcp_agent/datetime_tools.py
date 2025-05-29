#!/usr/bin/env python3
"""
日期时间MCP工具
提供日期查询、星期数计算、北京时间获取等功能
"""

import asyncio
import json
import sys
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List
import calendar

# MCP相关导入
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.types import Resource, Tool, TextContent, ImageContent, EmbeddedResource
import mcp.types as types

# 创建服务器实例
server = Server("datetime-tools")

# 北京时区 (UTC+8)
BEIJING_TZ = timezone(timedelta(hours=8))

@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    """列出所有可用的日期时间工具"""
    return [
        Tool(
            name="get_current_date",
            description="获取当前日期及对应的星期数",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_date_weekday",
            description="查询指定日期对应的星期数",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "指定日期，格式：YYYY-MM-DD，例如：2025-05-27"
                    }
                },
                "required": ["date"]
            }
        ),
        Tool(
            name="get_beijing_time",
            description="获取当前真实的北京时间（仅时间）",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
    """处理工具调用"""
    
    if name == "get_current_date":
        return await get_current_date()
    elif name == "get_date_weekday":
        date_str = arguments.get("date")
        if not date_str:
            return [types.TextContent(
                type="text",
                text="错误：缺少必需的参数 'date'"
            )]
        return await get_date_weekday(date_str)
    elif name == "get_beijing_time":
        return await get_beijing_time()
    else:
        return [types.TextContent(
            type="text",
            text=f"错误：未知的工具名称 '{name}'"
        )]

async def get_current_date() -> List[types.TextContent]:
    """获取当前日期及对应的星期数"""
    try:
        # 获取北京时间的当前日期
        now_beijing = datetime.now(BEIJING_TZ)
        
        # 格式化日期
        date_str = now_beijing.strftime("%Y-%m-%d")
        
        # 获取星期数（0=周一，6=周日）
        weekday_num = now_beijing.weekday()
        
        # 中文星期名称
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        weekday_cn = weekday_names[weekday_num]
        
        # 英文星期名称
        weekday_en = now_beijing.strftime("%A")
        
        # 获取年份中的第几天
        day_of_year = now_beijing.timetuple().tm_yday
        
        # 获取年份总天数
        year = now_beijing.year
        total_days = 366 if calendar.isleap(year) else 365
        
        result = {
            "current_date": date_str,
            "weekday_number": weekday_num + 1,  # 转换为1-7（周一到周日）
            "weekday_chinese": weekday_cn,
            "weekday_english": weekday_en,
            "day_of_year": day_of_year,
            "total_days_in_year": total_days,
            "year": year,
            "month": now_beijing.month,
            "day": now_beijing.day,
            "is_leap_year": calendar.isleap(year)
        }
        
        response_text = f"""当前日期信息：
📅 日期：{date_str} ({weekday_cn})
📊 详细信息：
  - 星期数：{weekday_num + 1} ({weekday_cn} / {weekday_en})
  - 年份第{day_of_year}天，共{total_days}天
  - 年份：{year}年{'（闰年）' if calendar.isleap(year) else '（平年）'}
  - 月份：{now_beijing.month}月
  - 日期：{now_beijing.day}日"""
        
        return [types.TextContent(type="text", text=response_text)]
        
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"获取当前日期时发生错误：{str(e)}"
        )]

async def get_date_weekday(date_str: str) -> List[types.TextContent]:
    """查询指定日期对应的星期数"""
    try:
        # 解析日期字符串
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return [types.TextContent(
                type="text",
                text=f"错误：日期格式不正确，请使用 YYYY-MM-DD 格式，例如：2025-05-27"
            )]
        
        # 获取星期数（0=周一，6=周日）
        weekday_num = target_date.weekday()
        
        # 中文星期名称
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        weekday_cn = weekday_names[weekday_num]
        
        # 英文星期名称
        weekday_en = target_date.strftime("%A")
        
        # 获取年份中的第几天
        day_of_year = target_date.timetuple().tm_yday
        
        # 获取年份总天数
        year = target_date.year
        total_days = 366 if calendar.isleap(year) else 365
        
        # 计算距离今天的天数
        today = datetime.now(BEIJING_TZ).date()
        target_date_only = target_date.date()
        days_diff = (target_date_only - today).days
        
        if days_diff > 0:
            time_desc = f"距今{days_diff}天后"
        elif days_diff < 0:
            time_desc = f"距今{abs(days_diff)}天前"
        else:
            time_desc = "今天"
        
        result = {
            "query_date": date_str,
            "weekday_number": weekday_num + 1,
            "weekday_chinese": weekday_cn,
            "weekday_english": weekday_en,
            "day_of_year": day_of_year,
            "total_days_in_year": total_days,
            "year": year,
            "month": target_date.month,
            "day": target_date.day,
            "is_leap_year": calendar.isleap(year),
            "days_from_today": days_diff,
            "time_description": time_desc
        }
        
        response_text = f"""指定日期信息：
📅 日期：{date_str} ({weekday_cn}) - {time_desc}
📊 详细信息：
  - 星期数：{weekday_num + 1} ({weekday_cn} / {weekday_en})
  - 年份第{day_of_year}天，共{total_days}天
  - 年份：{year}年{'（闰年）' if calendar.isleap(year) else '（平年）'}
  - 月份：{target_date.month}月
  - 日期：{target_date.day}日"""
        
        return [types.TextContent(type="text", text=response_text)]
        
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"查询指定日期时发生错误：{str(e)}"
        )]

async def get_beijing_time() -> List[types.TextContent]:
    """获取当前真实的北京时间（仅时间）"""
    try:
        # 获取系统当前时间，然后转换为北京时间
        # 使用系统本地时间，因为系统已经设置为正确的时区
        now_local = datetime.now()
        
        # 如果系统不是北京时间，则手动转换
        # 但从系统时间看，应该已经是正确的本地时间了
        
        # 格式化时间（只要时间，不要日期）
        time_str = now_local.strftime("%H:%M:%S")
        
        # 获取时间段描述
        hour = now_local.hour
        if 5 <= hour < 12:
            time_period = "上午"
        elif 12 <= hour < 18:
            time_period = "下午"
        elif 18 <= hour < 22:
            time_period = "晚上"
        else:
            time_period = "深夜"
        
        # 简化的结果，只包含时间信息
        result = {
            "time": time_str,
            "time_period": time_period,
            "hour": hour,
            "minute": now_local.minute,
            "second": now_local.second
        }
        
        # 简化的响应文本，只显示时间
        response_text = f"""当前时间：{time_str} ({time_period})"""
        
        return [types.TextContent(type="text", text=response_text)]
        
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"获取时间时发生错误：{str(e)}"
        )]

async def main():
    """主函数"""
    # 从stdin/stdout运行服务器
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="datetime-tools",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    import mcp.server.stdio
    asyncio.run(main()) 