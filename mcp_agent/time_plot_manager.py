"""
时间和剧情管理模块
负责获取北京时间、存储到Redis、解析角色剧情文件并提取当前时间段的内容
"""

import asyncio
import json
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

class TimePlotManager:
    """时间和剧情管理器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.beijing_timezone = timezone(timedelta(hours=8))
        
    async def get_beijing_time_from_redis(self) -> Optional[datetime]:
        """从Redis获取北京时间"""
        try:
            from database_config import get_redis_client
            redis_client = await get_redis_client()
            
            time_str = await redis_client.get("beijing_time")
            if time_str:
                # 处理可能的bytes类型
                if isinstance(time_str, bytes):
                    time_str = time_str.decode('utf-8')
                elif not isinstance(time_str, str):
                    time_str = str(time_str)
                
                # 解析时间字符串
                parsed_time = datetime.fromisoformat(time_str)
                self.logger.info(f"✅ 从Redis获取北京时间: {parsed_time}")
                return parsed_time
            
            self.logger.info("📝 Redis中没有存储的北京时间")
            return None
            
        except Exception as e:
            self.logger.error(f"❌ 从Redis获取北京时间失败: {e}")
            return None
    
    async def get_beijing_time_from_tool(self) -> Optional[datetime]:
        """从MCP工具获取北京时间"""
        try:
            # 这里需要调用MCP工具获取时间
            # 为了测试，我们先使用系统时间 + 8小时作为北京时间
            utc_now = datetime.now(timezone.utc)
            beijing_now = utc_now.astimezone(self.beijing_timezone)
            
            self.logger.info(f"从工具获取北京时间: {beijing_now}")
            return beijing_now
            
        except Exception as e:
            self.logger.error(f"从工具获取北京时间失败: {e}")
            return None
    
    async def store_beijing_time_to_redis(self, beijing_time: datetime, expire_minutes: int = 30) -> bool:
        """将北京时间存储到Redis"""
        try:
            from database_config import get_redis_client
            redis_client = await get_redis_client()
            
            # 存储时间字符串
            time_str = beijing_time.isoformat()
            await redis_client.setex("beijing_time", expire_minutes * 60, time_str)
            
            self.logger.info(f"北京时间已存储到Redis: {time_str}, 过期时间: {expire_minutes}分钟")
            return True
            
        except Exception as e:
            self.logger.error(f"存储北京时间到Redis失败: {e}")
            return False
    
    async def get_current_beijing_time(self) -> datetime:
        """获取当前北京时间（优先从Redis获取，如果没有则从工具获取）"""
        # 1. 先尝试从Redis获取
        beijing_time = await self.get_beijing_time_from_redis()
        
        if beijing_time is None:
            # 2. 如果Redis中没有，从工具获取并存储到Redis
            beijing_time = await self.get_beijing_time_from_tool()
            if beijing_time:
                await self.store_beijing_time_to_redis(beijing_time)
            else:
                # 3. 如果工具也失败，使用本地时间 + 8小时
                utc_now = datetime.now(timezone.utc)
                beijing_time = utc_now.astimezone(self.beijing_timezone)
                self.logger.warning(f"使用本地时间作为北京时间: {beijing_time}")
        
        return beijing_time
    
    def find_character_plot_file(self, role_id: str, date_str: str) -> Optional[str]:
        """查找角色剧情文件
        
        Args:
            role_id: 角色ID (如 chenxiaozhi_001)
            date_str: 日期字符串 (如 2025-06-03)
            
        Returns:
            文件路径，如果找到的话
        """
        try:
            # 使用完整的角色ID作为文件夹名
            role_folder_name = f"{role_id}_plot"
            
            # 构建剧情文件夹路径
            project_root = Path(__file__).parent.parent
            plot_dir = project_root / "character_plots" / role_folder_name
            
            self.logger.info(f"🔍 查找角色剧情文件夹: {plot_dir}")
            
            if not plot_dir.exists():
                self.logger.warning(f"⚠️ 角色剧情文件夹不存在: {plot_dir}")
                
                # 尝试查找其他可能的文件夹名（兼容性处理）
                alternate_names = [
                    f"{role_id.split('_')[0]}_plot",  # 只用角色名部分
                    f"{role_id.split('_')[0]}_{role_id.split('_')[1]}_plot" if '_' in role_id else None  # 角色名_编号_plot
                ]
                
                for alt_name in alternate_names:
                    if alt_name:
                        alt_dir = project_root / "character_plots" / alt_name
                        self.logger.info(f"🔍 尝试备用文件夹: {alt_dir}")
                        if alt_dir.exists():
                            plot_dir = alt_dir
                            self.logger.info(f"✅ 找到备用文件夹: {plot_dir}")
                            break
                else:
                    return None
            
            # 查找以指定日期开头的txt文件
            matching_files = list(plot_dir.glob(f"{date_str}*.txt"))
            self.logger.info(f"🔍 在文件夹 {plot_dir} 中查找以 {date_str} 开头的文件，找到 {len(matching_files)} 个")
            
            for file_path in matching_files:
                self.logger.info(f"✅ 找到角色剧情文件: {file_path}")
                return str(file_path)
            
            self.logger.info(f"📝 未找到角色 {role_id} 在 {date_str} 的剧情文件")
            return None
            
        except Exception as e:
            self.logger.error(f"❌ 查找角色剧情文件失败: {e}")
            return None
    
    def parse_plot_file_content(self, file_path: str) -> List[Dict[str, Any]]:
        """解析剧情文件内容，提取所有时间段行
        
        Args:
            file_path: 剧情文件路径
            
        Returns:
            包含时间段信息的字典列表
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.split('\n')
            time_segments = []
            
            # 正则表达式匹配时间段格式 (如: 8:00-8:30, 10:00-12:00)
            time_pattern = r'^(\d{1,2}:\d{2})-(\d{1,2}:\d{2}|\w+:\w+)\s+(.+)$'
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                match = re.match(time_pattern, line)
                
                if match:
                    start_time_str = match.group(1)
                    end_time_str = match.group(2)
                    content_part = match.group(3)
                    
                    # 解析开始时间
                    try:
                        start_hour, start_minute = map(int, start_time_str.split(':'))
                        start_minutes = start_hour * 60 + start_minute
                    except:
                        continue
                    
                    # 解析结束时间（可能是xx:xx格式）
                    end_minutes = None
                    if end_time_str and not 'xx' in end_time_str.lower():
                        try:
                            end_hour, end_minute = map(int, end_time_str.split(':'))
                            end_minutes = end_hour * 60 + end_minute
                        except:
                            pass
                    
                    time_segments.append({
                        'line_number': line_num,
                        'start_time': start_time_str,
                        'end_time': end_time_str,
                        'start_minutes': start_minutes,
                        'end_minutes': end_minutes,
                        'content': content_part,
                        'full_line': line
                    })
            
            self.logger.info(f"从文件 {file_path} 解析出 {len(time_segments)} 个时间段")
            return time_segments
            
        except Exception as e:
            self.logger.error(f"解析剧情文件内容失败: {e}")
            return []
    
    def get_current_time_content(self, time_segments: List[Dict[str, Any]], current_time: datetime) -> List[str]:
        """根据当前时间获取对应的时间段内容
        
        Args:
            time_segments: 时间段列表
            current_time: 当前时间
            
        Returns:
            匹配的时间段内容列表
        """
        try:
            current_minutes = current_time.hour * 60 + current_time.minute
            matched_contents = []
            
            if not time_segments:
                self.logger.warning("⚠️ 没有可用的时间段数据")
                return []
            
            self.logger.info(f"🕒 当前时间: {current_time.strftime('%H:%M')} (总分钟数: {current_minutes})")
            self.logger.info(f"📊 开始匹配 {len(time_segments)} 个时间段:")
            
            # 获取最早和最晚的时间段
            earliest_segment = min(time_segments, key=lambda x: x['start_minutes'])
            latest_segment = max(time_segments, key=lambda x: x['start_minutes'])
            
            earliest_time = earliest_segment['start_minutes']
            # 找到最晚的结束时间
            latest_end_time = latest_segment['end_minutes'] if latest_segment['end_minutes'] else latest_segment['start_minutes']
            for segment in time_segments:
                if segment['end_minutes'] and segment['end_minutes'] > latest_end_time:
                    latest_end_time = segment['end_minutes']
            
            self.logger.info(f"📋 剧情时间范围: {earliest_time//60:02d}:{earliest_time%60:02d} - {latest_end_time//60:02d}:{latest_end_time%60:02d}")
            
            # 🚀 智能时间匹配逻辑
            if current_minutes < earliest_time:
                self.logger.warning(f"⏰ 当前时间 {current_time.strftime('%H:%M')} 早于剧情最早时间，尝试加载前一天的剧情...")
                # 尝试加载前一天的剧情
                yesterday_content = self._load_previous_day_plot(current_time)
                if yesterday_content:
                    return yesterday_content
                else:
                    self.logger.info(f"💡 未找到前一天剧情，加载当天第一个时间段作为基准")
                    # 返回第一个时间段及其之前的内容（通常就是第一个）
                    first_segment_line = earliest_segment['line_number']
                    for segment in time_segments:
                        if segment['line_number'] <= first_segment_line:
                            matched_contents.append(segment['full_line'])
                    return matched_contents
                    
            elif current_minutes >= latest_end_time:
                self.logger.info(f"🌙 当前时间 {current_time.strftime('%H:%M')} 晚于剧情最晚时间，加载最后一个时间段的内容")
                # 当前时间晚于所有剧情时间，加载最后一个时间段的所有内容
                latest_segment_line = latest_segment['line_number']
                # 找到最大的行号
                max_line = max(segment['line_number'] for segment in time_segments)
                for segment in time_segments:
                    if segment['line_number'] <= max_line:
                        matched_contents.append(segment['full_line'])
                self.logger.info(f"✅ 晚于剧情时间，加载所有 {len(matched_contents)} 个时间段的内容（角色已经历了一天的所有事件）")
                return matched_contents
            
            # 正常时间匹配逻辑
            target_segment = None
            for i, segment in enumerate(time_segments, 1):
                start_minutes = segment['start_minutes']
                end_minutes = segment['end_minutes']
                
                self.logger.info(f"  {i}. {segment['start_time']}-{segment['end_time']} "
                               f"(分钟: {start_minutes}-{end_minutes if end_minutes else 'xx'})")
                
                # 如果结束时间存在，检查当前时间是否在时间段内
                if end_minutes is not None:
                    if start_minutes <= current_minutes < end_minutes:
                        target_segment = segment
                        self.logger.info(f"    ✅ 匹配！当前时间 {current_minutes} 在范围 [{start_minutes}, {end_minutes}) 内")
                        break
                    else:
                        self.logger.info(f"    ❌ 不匹配，当前时间 {current_minutes} 不在范围 [{start_minutes}, {end_minutes}) 内")
                else:
                    # 如果结束时间是xx:xx格式，检查是否是最后一个可能的时间段
                    if start_minutes <= current_minutes:
                        target_segment = segment
                        self.logger.info(f"    ⭐ 可能匹配（开放结束时间），当前时间 {current_minutes} >= {start_minutes}")
                        # 继续查找，看是否有更精确的匹配
                    else:
                        self.logger.info(f"    ❌ 不匹配，当前时间 {current_minutes} < {start_minutes}")
            
            if target_segment:
                # 获取目标时间段及之前所有有时间段的内容
                target_line = target_segment['line_number']
                self.logger.info(f"🎯 找到目标时间段: 第{target_line}行 - {target_segment['start_time']}-{target_segment['end_time']}")
                self.logger.info(f"📝 获取第{target_line}行及之前所有时间段内容:")
                
                for segment in time_segments:
                    if segment['line_number'] <= target_line:
                        matched_contents.append(segment['full_line'])
                        self.logger.info(f"  ✅ 第{segment['line_number']}行: {segment['full_line'][:80]}...")
                
                self.logger.info(f"✅ 当前时间 {current_time.strftime('%H:%M')} 匹配到 {len(matched_contents)} 行内容")
            else:
                self.logger.warning(f"⚠️ 当前时间 {current_time.strftime('%H:%M')} 未匹配到任何时间段，尝试加载最接近的时间段")
                # 如果没有精确匹配，找最接近的时间段
                closest_segment = min(time_segments, key=lambda x: abs(x['start_minutes'] - current_minutes))
                target_line = closest_segment['line_number']
                for segment in time_segments:
                    if segment['line_number'] <= target_line:
                        matched_contents.append(segment['full_line'])
                self.logger.info(f"🎯 使用最接近的时间段: {closest_segment['start_time']}-{closest_segment['end_time']}，加载 {len(matched_contents)} 行内容")
            
            return matched_contents
            
        except Exception as e:
            self.logger.error(f"❌ 获取当前时间内容失败: {e}")
            return []
    
    def _load_previous_day_plot(self, current_time: datetime) -> List[str]:
        """加载前一天的剧情内容"""
        try:
            from datetime import timedelta
            
            # 计算前一天的日期
            previous_day = current_time - timedelta(days=1)
            date_str = previous_day.strftime('%Y-%m-%d')
            
            self.logger.info(f"🔍 尝试查找前一天 {date_str} 的剧情文件...")
            
            # 这里需要从当前角色上下文获取role_id，暂时使用一个默认逻辑
            # 在实际调用中，应该传入role_id参数
            role_folders = [
                "chenxiaozhi_001_plot",
                "lingye_001_plot"
            ]
            
            for role_folder in role_folders:
                plot_file = self.find_character_plot_file_by_folder(role_folder, date_str)
                if plot_file:
                    self.logger.info(f"✅ 找到前一天剧情文件: {plot_file}")
                    time_segments = self.parse_plot_file_content(plot_file)
                    if time_segments:
                        # 返回前一天的所有剧情内容
                        all_content = [segment['full_line'] for segment in time_segments]
                        self.logger.info(f"📚 加载前一天完整剧情: {len(all_content)} 个时间段")
                        return all_content
            
            self.logger.warning(f"⚠️ 未找到前一天 {date_str} 的剧情文件")
            return []
            
        except Exception as e:
            self.logger.error(f"❌ 加载前一天剧情失败: {e}")
            return []
    
    def find_character_plot_file_by_folder(self, role_folder: str, date_str: str) -> Optional[str]:
        """根据角色文件夹和日期查找剧情文件"""
        try:
            current_dir = Path(__file__).parent.parent
            character_plots_dir = current_dir / "character_plots" / role_folder
            
            if not character_plots_dir.exists():
                return None
            
            # 查找以日期开头的文件
            for file_path in character_plots_dir.glob(f"{date_str}*.txt"):
                if file_path.is_file():
                    return str(file_path)
            
            return None
            
        except Exception as e:
            self.logger.error(f"查找角色剧情文件失败: {e}")
            return None
    
    async def get_role_current_plot_content(self, role_id: str) -> List[str]:
        """获取角色当前时间的剧情内容
        
        Args:
            role_id: 角色ID
            
        Returns:
            当前时间段的剧情内容列表
        """
        try:
            # 1. 获取当前北京时间
            current_time = await self.get_current_beijing_time()
            date_str = current_time.strftime('%Y-%m-%d')
            
            self.logger.info(f"获取角色 {role_id} 在 {date_str} {current_time.strftime('%H:%M')} 的剧情内容")
            
            # 2. 查找剧情文件
            plot_file = self.find_character_plot_file(role_id, date_str)
            if not plot_file:
                return []
            
            # 3. 解析剧情文件
            time_segments = self.parse_plot_file_content(plot_file)
            if not time_segments:
                return []
            
            # 4. 获取当前时间段的内容（传递role_id用于前一天剧情加载）
            current_content = self.get_current_time_content_with_role(time_segments, current_time, role_id)
            return current_content
            
        except Exception as e:
            self.logger.error(f"获取角色当前剧情内容失败: {e}")
            return []
    
    def get_current_time_content_with_role(self, time_segments: List[Dict[str, Any]], current_time: datetime, role_id: str) -> List[str]:
        """根据当前时间获取对应的时间段内容（支持角色ID）
        
        Args:
            time_segments: 时间段列表
            current_time: 当前时间
            role_id: 角色ID
            
        Returns:
            匹配的时间段内容列表
        """
        try:
            current_minutes = current_time.hour * 60 + current_time.minute
            matched_contents = []
            
            if not time_segments:
                self.logger.warning("⚠️ 没有可用的时间段数据")
                return []
            
            self.logger.info(f"🕒 当前时间: {current_time.strftime('%H:%M')} (总分钟数: {current_minutes})")
            self.logger.info(f"📊 开始匹配 {len(time_segments)} 个时间段:")
            
            # 获取最早和最晚的时间段
            earliest_segment = min(time_segments, key=lambda x: x['start_minutes'])
            latest_segment = max(time_segments, key=lambda x: x['start_minutes'])
            
            earliest_time = earliest_segment['start_minutes']
            # 找到最晚的结束时间
            latest_end_time = latest_segment['end_minutes'] if latest_segment['end_minutes'] else latest_segment['start_minutes']
            for segment in time_segments:
                if segment['end_minutes'] and segment['end_minutes'] > latest_end_time:
                    latest_end_time = segment['end_minutes']
            
            self.logger.info(f"📋 剧情时间范围: {earliest_time//60:02d}:{earliest_time%60:02d} - {latest_end_time//60:02d}:{latest_end_time%60:02d}")
            
            # 🚀 智能时间匹配逻辑
            if current_minutes < earliest_time:
                self.logger.warning(f"⏰ 当前时间 {current_time.strftime('%H:%M')} 早于剧情最早时间，尝试加载前一天的剧情...")
                # 尝试加载前一天的剧情
                yesterday_content = self._load_previous_day_plot_with_role(current_time, role_id)
                if yesterday_content:
                    return yesterday_content
                else:
                    self.logger.info(f"💡 未找到前一天剧情，加载当天第一个时间段作为基准")
                    # 返回第一个时间段及其之前的内容（通常就是第一个）
                    first_segment_line = earliest_segment['line_number']
                    for segment in time_segments:
                        if segment['line_number'] <= first_segment_line:
                            matched_contents.append(segment['full_line'])
                    return matched_contents
                    
            elif current_minutes >= latest_end_time:
                self.logger.info(f"🌙 当前时间 {current_time.strftime('%H:%M')} 晚于剧情最晚时间，加载最后一个时间段的内容")
                # 当前时间晚于所有剧情时间，加载最后一个时间段的所有内容
                latest_segment_line = latest_segment['line_number']
                # 找到最大的行号
                max_line = max(segment['line_number'] for segment in time_segments)
                for segment in time_segments:
                    if segment['line_number'] <= max_line:
                        matched_contents.append(segment['full_line'])
                self.logger.info(f"✅ 晚于剧情时间，加载所有 {len(matched_contents)} 个时间段的内容（角色已经历了一天的所有事件）")
                return matched_contents
            
            # 正常时间匹配逻辑
            target_segment = None
            for i, segment in enumerate(time_segments, 1):
                start_minutes = segment['start_minutes']
                end_minutes = segment['end_minutes']
                
                self.logger.info(f"  {i}. {segment['start_time']}-{segment['end_time']} "
                               f"(分钟: {start_minutes}-{end_minutes if end_minutes else 'xx'})")
                
                # 如果结束时间存在，检查当前时间是否在时间段内
                if end_minutes is not None:
                    if start_minutes <= current_minutes < end_minutes:
                        target_segment = segment
                        self.logger.info(f"    ✅ 匹配！当前时间 {current_minutes} 在范围 [{start_minutes}, {end_minutes}) 内")
                        break
                    else:
                        self.logger.info(f"    ❌ 不匹配，当前时间 {current_minutes} 不在范围 [{start_minutes}, {end_minutes}) 内")
                else:
                    # 如果结束时间是xx:xx格式，检查是否是最后一个可能的时间段
                    if start_minutes <= current_minutes:
                        target_segment = segment
                        self.logger.info(f"    ⭐ 可能匹配（开放结束时间），当前时间 {current_minutes} >= {start_minutes}")
                        # 继续查找，看是否有更精确的匹配
                    else:
                        self.logger.info(f"    ❌ 不匹配，当前时间 {current_minutes} < {start_minutes}")
            
            if target_segment:
                # 获取目标时间段及之前所有有时间段的内容
                target_line = target_segment['line_number']
                self.logger.info(f"🎯 找到目标时间段: 第{target_line}行 - {target_segment['start_time']}-{target_segment['end_time']}")
                self.logger.info(f"📝 获取第{target_line}行及之前所有时间段内容:")
                
                for segment in time_segments:
                    if segment['line_number'] <= target_line:
                        matched_contents.append(segment['full_line'])
                        self.logger.info(f"  ✅ 第{segment['line_number']}行: {segment['full_line'][:80]}...")
                
                self.logger.info(f"✅ 当前时间 {current_time.strftime('%H:%M')} 匹配到 {len(matched_contents)} 行内容")
            else:
                self.logger.warning(f"⚠️ 当前时间 {current_time.strftime('%H:%M')} 未匹配到任何时间段，尝试加载最接近的时间段")
                # 如果没有精确匹配，找最接近的时间段
                closest_segment = min(time_segments, key=lambda x: abs(x['start_minutes'] - current_minutes))
                target_line = closest_segment['line_number']
                for segment in time_segments:
                    if segment['line_number'] <= target_line:
                        matched_contents.append(segment['full_line'])
                self.logger.info(f"🎯 使用最接近的时间段: {closest_segment['start_time']}-{closest_segment['end_time']}，加载 {len(matched_contents)} 行内容")
            
            return matched_contents
            
        except Exception as e:
            self.logger.error(f"❌ 获取当前时间内容失败: {e}")
            return []
    
    def _load_previous_day_plot_with_role(self, current_time: datetime, role_id: str) -> List[str]:
        """根据角色ID加载前一天的剧情内容"""
        try:
            from datetime import timedelta
            
            # 计算前一天的日期
            previous_day = current_time - timedelta(days=1)
            date_str = previous_day.strftime('%Y-%m-%d')
            
            self.logger.info(f"🔍 尝试查找角色 {role_id} 前一天 {date_str} 的剧情文件...")
            
            # 首先尝试查找指定角色的前一天剧情
            plot_file = self.find_character_plot_file(role_id, date_str)
            if plot_file:
                self.logger.info(f"✅ 找到角色 {role_id} 前一天剧情文件: {plot_file}")
                time_segments = self.parse_plot_file_content(plot_file)
                if time_segments:
                    # 返回前一天的所有剧情内容
                    all_content = [segment['full_line'] for segment in time_segments]
                    self.logger.info(f"📚 加载角色 {role_id} 前一天完整剧情: {len(all_content)} 个时间段")
                    return all_content
            
            self.logger.warning(f"⚠️ 未找到角色 {role_id} 前一天 {date_str} 的剧情文件")
            return []
            
        except Exception as e:
            self.logger.error(f"❌ 加载角色 {role_id} 前一天剧情失败: {e}")
            return []
    
    async def update_time_and_get_plot_content(self, role_id: str) -> List[str]:
        """更新时间并获取剧情内容（用于定时任务）"""
        try:
            # 强制更新时间
            beijing_time = await self.get_beijing_time_from_tool()
            if beijing_time:
                await self.store_beijing_time_to_redis(beijing_time)
            
            # 获取剧情内容
            return await self.get_role_current_plot_content(role_id)
            
        except Exception as e:
            self.logger.error(f"更新时间并获取剧情内容失败: {e}")
            return []


async def test_time_plot_manager():
    """测试时间和剧情管理器"""
    print("🕒 测试时间和剧情管理器...")
    
    manager = TimePlotManager()
    
    # 测试获取北京时间
    print("\n1. 测试获取北京时间:")
    beijing_time = await manager.get_current_beijing_time()
    print(f"当前北京时间: {beijing_time}")
    
    # 测试查找剧情文件
    print("\n2. 测试查找剧情文件:")
    role_id = "chenxiaozhi_001"
    date_str = beijing_time.strftime('%Y-%m-%d')
    
    plot_file = manager.find_character_plot_file(role_id, date_str)
    if plot_file:
        print(f"找到剧情文件: {plot_file}")
        
        # 测试解析剧情文件
        print("\n3. 测试解析剧情文件:")
        time_segments = manager.parse_plot_file_content(plot_file)
        print(f"解析出 {len(time_segments)} 个时间段:")
        for i, segment in enumerate(time_segments[:5], 1):  # 只显示前5个
            print(f"  {i}. {segment['start_time']}-{segment['end_time']}: {segment['content'][:50]}...")
        
        # 测试获取当前时间内容
        print("\n4. 测试获取当前时间内容:")
        current_content = manager.get_current_time_content(time_segments, beijing_time)
        if current_content:
            print(f"当前时间 {beijing_time.strftime('%H:%M')} 匹配到 {len(current_content)} 行内容:")
            for i, content in enumerate(current_content, 1):
                print(f"  {i}. {content}")
        else:
            print(f"当前时间 {beijing_time.strftime('%H:%M')} 没有匹配的内容")
    else:
        print(f"未找到角色 {role_id} 在 {date_str} 的剧情文件")
    
    # 测试完整流程
    print("\n5. 测试完整流程:")
    plot_content = await manager.get_role_current_plot_content(role_id)
    if plot_content:
        print(f"获取到 {len(plot_content)} 行剧情内容:")
        for i, content in enumerate(plot_content, 1):
            print(f"  {i}. {content}")
    else:
        print("未获取到剧情内容")


if __name__ == "__main__":
    asyncio.run(test_time_plot_manager()) 