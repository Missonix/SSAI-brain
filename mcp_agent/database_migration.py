"""
数据库迁移脚本
用于更新role_details表结构
"""

import logging
import asyncio
from database_config import get_mysql_session, init_all_databases
from sqlalchemy import text

logger = logging.getLogger(__name__)

async def migrate_role_details_table():
    """迁移role_details表结构"""
    try:
        async with get_mysql_session() as session:
            logger.info("开始迁移role_details表结构...")
            
            # 1. 检查当前表结构
            check_columns_sql = """
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'role_details' 
            AND TABLE_SCHEMA = DATABASE()
            """
            
            result = await session.execute(text(check_columns_sql))
            existing_columns = [row[0] for row in result.fetchall()]
            logger.info(f"当前表字段: {existing_columns}")
            
            # 2. 重命名字段 p0_prompt_path -> L0_prompt_path
            if 'p0_prompt_path' in existing_columns and 'L0_prompt_path' not in existing_columns:
                logger.info("重命名字段: p0_prompt_path -> L0_prompt_path")
                await session.execute(text(
                    "ALTER TABLE role_details CHANGE COLUMN p0_prompt_path L0_prompt_path VARCHAR(512) NOT NULL COMMENT 'L0提示词文件路径'"
                ))
            
            # 3. 重命名字段 p1_prompt_path -> L1_prompt_path
            if 'p1_prompt_path' in existing_columns and 'L1_prompt_path' not in existing_columns:
                logger.info("重命名字段: p1_prompt_path -> L1_prompt_path")
                await session.execute(text(
                    "ALTER TABLE role_details CHANGE COLUMN p1_prompt_path L1_prompt_path VARCHAR(512) NOT NULL COMMENT 'L1提示词文件路径'"
                ))
            
            # 4. 添加新字段 age
            if 'age' not in existing_columns:
                logger.info("添加新字段: age")
                await session.execute(text(
                    "ALTER TABLE role_details ADD COLUMN age INT COMMENT '年龄'"
                ))
            
            # 5. 添加新字段 current_life_stage_id
            if 'current_life_stage_id' not in existing_columns:
                logger.info("添加新字段: current_life_stage_id")
                await session.execute(text(
                    "ALTER TABLE role_details ADD COLUMN current_life_stage_id VARCHAR(64) COMMENT '当前生活阶段ID'"
                ))
            
            # 6. 添加新字段 current_plot_segment_id
            if 'current_plot_segment_id' not in existing_columns:
                logger.info("添加新字段: current_plot_segment_id")
                await session.execute(text(
                    "ALTER TABLE role_details ADD COLUMN current_plot_segment_id VARCHAR(64) COMMENT '当前剧情段落ID'"
                ))
            
            # 7. 添加新字段 current_materials_id
            if 'current_materials_id' not in existing_columns:
                logger.info("添加新字段: current_materials_id")
                await session.execute(text(
                    "ALTER TABLE role_details ADD COLUMN current_materials_id VARCHAR(64) COMMENT '当前材料ID'"
                ))
            
            await session.commit()
            logger.info("✅ role_details表结构迁移完成")
            
            # 验证迁移结果
            result = await session.execute(text(check_columns_sql))
            updated_columns = [row[0] for row in result.fetchall()]
            logger.info(f"迁移后表字段: {updated_columns}")
            
    except Exception as e:
        logger.error(f"❌ 迁移role_details表结构失败: {e}")
        raise

async def rollback_role_details_table():
    """回滚role_details表结构（仅供紧急情况使用）"""
    try:
        async with get_mysql_session() as session:
            logger.info("开始回滚role_details表结构...")
            
            # 检查当前表结构
            check_columns_sql = """
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'role_details' 
            AND TABLE_SCHEMA = DATABASE()
            """
            
            result = await session.execute(text(check_columns_sql))
            existing_columns = [row[0] for row in result.fetchall()]
            
            # 回滚字段名称
            if 'L0_prompt_path' in existing_columns:
                logger.info("回滚字段: L0_prompt_path -> p0_prompt_path")
                await session.execute(text(
                    "ALTER TABLE role_details CHANGE COLUMN L0_prompt_path p0_prompt_path VARCHAR(512) NOT NULL COMMENT 'L0提示词文件路径'"
                ))
            
            if 'L1_prompt_path' in existing_columns:
                logger.info("回滚字段: L1_prompt_path -> p1_prompt_path")
                await session.execute(text(
                    "ALTER TABLE role_details CHANGE COLUMN L1_prompt_path p1_prompt_path VARCHAR(512) NOT NULL COMMENT 'L1提示词文件路径'"
                ))
            
            # 删除新增字段（谨慎操作，会丢失数据）
            for column in ['age', 'current_life_stage_id', 'current_plot_segment_id', 'current_materials_id']:
                if column in existing_columns:
                    logger.warning(f"删除字段: {column} (数据将丢失)")
                    await session.execute(text(f"ALTER TABLE role_details DROP COLUMN {column}"))
            
            await session.commit()
            logger.info("✅ role_details表结构回滚完成")
            
    except Exception as e:
        logger.error(f"❌ 回滚role_details表结构失败: {e}")
        raise

async def main():
    """主函数"""
    import sys
    
    # 初始化数据库连接
    try:
        logger.info("正在初始化数据库连接...")
        db_success = await init_all_databases()
        if not db_success:
            logger.error("数据库初始化失败")
            return
        logger.info("数据库连接初始化成功")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        return
    
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        # 回滚操作
        confirm = input("⚠️  警告：回滚操作将删除新增字段并可能导致数据丢失！确认执行吗？(yes/no): ")
        if confirm.lower() == 'yes':
            await rollback_role_details_table()
        else:
            print("取消回滚操作")
    else:
        # 迁移操作
        await migrate_role_details_table()

if __name__ == "__main__":
    asyncio.run(main()) 