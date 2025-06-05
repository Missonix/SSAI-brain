"""
角色生命系统初始化脚本
创建数据表并初始化测试数据
"""

import asyncio
import uuid
from datetime import date, datetime
from character_life_system.database_manager import character_life_manager
from character_life_system.models import (
    LifePlotOutlineData, LifeStageData, PlotSegmentData, SpecificPlotData,
    StageStatusEnum, SegmentStatusEnum, PlotStatusEnum
)

async def init_character_life_system():
    """初始化角色生命系统"""
    print("🎭 开始初始化角色生命系统...")
    print("=" * 70)
    
    try:
        # 0. 初始化数据库连接
        print("💾 初始化数据库连接...")
        from mcp_agent.database_config_forlife import init_all_databases
        db_success = await init_all_databases()
        if not db_success:
            print("❌ 数据库连接初始化失败")
            return
        print("✅ 数据库连接初始化成功")
        
        # 1. 创建数据表
        print("\n📊 创建角色生命系统数据表...")
        await character_life_manager.create_all_tables()
        print("✅ 数据表创建完成")
        
        # 2. 创建示例数据
        print("\n📝 创建示例角色生命大纲...")
        await create_sample_data()
        print("✅ 示例数据创建完成")
        
        print("\n🎉 角色生命系统初始化完成！")
        
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        raise

async def create_sample_data():
    """创建示例数据"""
    
    # 1. 创建角色生命大纲
    outline_id = str(uuid.uuid4())
    role_id = "chenxiaozhi_001"  # 对应现有角色
    
    outline_data = LifePlotOutlineData(
        outline_id=outline_id,
        role_id=role_id,
        role_name="陈小智",
        title="一个程序员的成长与蜕变之路",
        birthday=date(1995, 6, 15),
        life=95,
        wealth="中等",
        overall_theme="从初出茅庐的新手程序员成长为技术专家和团队领导者，经历职场起伏、技术挑战、人际关系处理，以及个人价值观的建立和完善。",
        version=1
    )
    
    success = await character_life_manager.create_life_plot_outline(outline_data)
    if success:
        print(f"  ✅ 创建生命大纲: {outline_data.title}")
    
        # 2. 创建生命阶段
        stages_data = [
            {
                "life_stage_id": str(uuid.uuid4()),
                "sequence_order": 1,
                "life_period": "2017-2019",
                "title": "初入职场",
                "description_for_plot_llm": "作为新毕业生进入软件公司，面对真实的工作环境和职场文化。这个阶段充满了学习、适应和初期的技术挑战。角色会经历从学生到职业人的身份转换，建立职业技能和工作习惯。",
                "stage_goals": "适应职场环境，掌握基础工作技能，建立职业人际关系，完成从学生到职业人的转变。",
                "status": StageStatusEnum.COMPLETED
            },
            {
                "life_stage_id": str(uuid.uuid4()),
                "sequence_order": 2,
                "life_period": "2019-2021",
                "title": "技能提升期",
                "description_for_plot_llm": "经过初期适应后，开始专注于技术能力的深度提升。面临更复杂的项目挑战，开始承担一定的技术责任。这个阶段会有技术突破的喜悦，也会有面对复杂问题时的困惑和压力。",
                "stage_goals": "深化技术专业能力，参与重要项目开发，获得同事和上级的认可，为后续晋升做准备。",
                "status": StageStatusEnum.ACTIVE
            },
            {
                "life_stage_id": str(uuid.uuid4()),
                "sequence_order": 3,
                "life_period": "2021-2023",
                "title": "职业发展期",
                "description_for_plot_llm": "开始承担更多责任，可能涉及团队协作、项目管理或技术指导工作。面临职业发展方向的选择，在技术专家和管理路线之间思考。这个阶段会有晋升机会，也会面对更大的工作压力和责任。",
                "stage_goals": "获得晋升或承担更重要角色，在技术和管理能力间找到平衡，建立个人职业品牌。",
                "status": StageStatusEnum.LOCKED
            },
            {
                "life_stage_id": str(uuid.uuid4()),
                "sequence_order": 4,
                "life_period": "2023-2025",
                "title": "中年危机与蜕变",
                "description_for_plot_llm": "进入职业生涯的关键转折期，可能面临行业变化、技术更新换代的挑战。需要重新思考职业方向和人生目标，可能会有跳槽、创业或转型的想法。这是一个充满变化和不确定性的阶段。",
                "stage_goals": "重新定位职业发展方向，适应行业变化，实现个人突破和价值重塑。",
                "status": StageStatusEnum.LOCKED
            }
        ]
        
        created_stages = []
        for stage_info in stages_data:
            stage_data = LifeStageData(
                life_stage_id=stage_info["life_stage_id"],
                outline_id=outline_id,
                sequence_order=stage_info["sequence_order"],
                life_period=stage_info["life_period"],
                title=stage_info["title"],
                description_for_plot_llm=stage_info["description_for_plot_llm"],
                stage_goals=stage_info["stage_goals"],
                status=stage_info["status"]
            )
            
            success = await character_life_manager.create_life_stage(stage_data)
            if success:
                print(f"    ✅ 创建生命阶段: {stage_data.title}")
                created_stages.append(stage_data)
        
        # 3. 为"技能提升期"创建剧情片段
        if len(created_stages) >= 2:
            active_stage = created_stages[1]  # 技能提升期
            
            segments_data = [
                {
                    "plot_segment_id": str(uuid.uuid4()),
                    "sequence_order_in_stage": 1,
                    "title": "重要项目分配",
                    "segment_prompt_for_plot_llm": "陈小智被分配到一个对公司很重要的新项目中，这是他职业生涯中接触到的最复杂的技术挑战。项目涉及新的技术栈，需要与多个团队协作，时间紧迫。这对他来说既是机会也是压力。",
                    "duration_in_days_estimate": 3,
                    "expected_emotional_arc": "初期兴奋和紧张 -> 遇到技术难题时的焦虑 -> 通过努力学习和请教获得突破的成就感",
                    "key_npcs_involved": "项目经理老王(严格但公正)、技术导师李姐(经验丰富，愿意指导)、同期新人小张(竞争对手但也是学习伙伴)",
                    "status": SegmentStatusEnum.ACTIVE,
                    "is_milestone_event": True
                },
                {
                    "plot_segment_id": str(uuid.uuid4()),
                    "sequence_order_in_stage": 2,
                    "title": "技术攻关期",
                    "segment_prompt_for_plot_llm": "项目进入关键的技术攻关阶段，陈小智需要解决一个核心技术难题。这个问题困扰团队很久，如果解决了会显著提升他在团队中的地位。他需要深入研究新技术，加班加点，同时平衡学习和交付压力。",
                    "duration_in_days_estimate": 7,
                    "expected_emotional_arc": "面对难题的困惑和压力 -> 深入研究时的专注和投入 -> 找到解决方案时的兴奋和满足",
                    "key_npcs_involved": "技术总监老陈(最终决策者)、产品经理小美(需求方，有时会增加压力)、运维工程师老吴(实施和部署的关键人物)",
                    "status": SegmentStatusEnum.LOCKED,
                    "is_milestone_event": True
                },
                {
                    "plot_segment_id": str(uuid.uuid4()),
                    "sequence_order_in_stage": 3,
                    "title": "项目验收与反思",
                    "segment_prompt_for_plot_llm": "项目进入最终验收阶段，陈小智的技术方案得到了验证和认可。在项目总结会上，他的贡献得到了公开表扬。这是他职业生涯的一个重要里程碑，让他对自己的能力有了新的认识。",
                    "duration_in_days_estimate": 2,
                    "expected_emotional_arc": "验收前的紧张和期待 -> 获得认可时的自豪和成就感 -> 对未来发展的憧憬和规划",
                    "key_npcs_involved": "部门总监(给予正式认可)、HR主管(可能涉及升职加薪讨论)、团队成员们(庆祝和感谢)",
                    "status": SegmentStatusEnum.LOCKED,
                    "is_milestone_event": False
                }
            ]
            
            created_segments = []
            for segment_info in segments_data:
                segment_data = PlotSegmentData(
                    plot_segment_id=segment_info["plot_segment_id"],
                    life_stage_id=active_stage.life_stage_id,
                    sequence_order_in_stage=segment_info["sequence_order_in_stage"],
                    title=segment_info["title"],
                    segment_prompt_for_plot_llm=segment_info["segment_prompt_for_plot_llm"],
                    duration_in_days_estimate=segment_info["duration_in_days_estimate"],
                    expected_emotional_arc=segment_info["expected_emotional_arc"],
                    key_npcs_involved=segment_info["key_npcs_involved"],
                    status=segment_info["status"],
                    is_milestone_event=segment_info["is_milestone_event"]
                )
                
                success = await character_life_manager.create_plot_segment(segment_data)
                if success:
                    print(f"      ✅ 创建剧情片段: {segment_data.title}")
                    created_segments.append(segment_data)
            
            # 4. 为"重要项目分配"创建具体剧情
            if created_segments:
                active_segment = created_segments[0]  # 重要项目分配
                
                plots_data = [
                    {
                        "plot_id": str(uuid.uuid4()),
                        "plot_order": 1,
                        "plot_date": "2020-03-15 am",
                        "plot_content_path": "plots/chenxiaozhi/project_assignment_day1_morning.txt",
                        "status": PlotStatusEnum.COMPLETED
                    },
                    {
                        "plot_id": str(uuid.uuid4()),
                        "plot_order": 2,
                        "plot_date": "2020-03-15 pm",
                        "plot_content_path": "plots/chenxiaozhi/project_assignment_day1_afternoon.txt",
                        "status": PlotStatusEnum.COMPLETED
                    },
                    {
                        "plot_id": str(uuid.uuid4()),
                        "plot_order": 3,
                        "plot_date": "2020-03-16 am",
                        "plot_content_path": "plots/chenxiaozhi/project_assignment_day2_morning.txt",
                        "status": PlotStatusEnum.ACTIVE
                    }
                ]
                
                for plot_info in plots_data:
                    plot_data = SpecificPlotData(
                        plot_id=plot_info["plot_id"],
                        plot_segment_id=active_segment.plot_segment_id,
                        plot_order=plot_info["plot_order"],
                        plot_date=plot_info["plot_date"],
                        plot_content_path=plot_info["plot_content_path"],
                        status=plot_info["status"]
                    )
                    
                    success = await character_life_manager.create_specific_plot(plot_data)
                    if success:
                        print(f"        ✅ 创建具体剧情: {plot_data.plot_date}")

async def test_character_life_system():
    """测试角色生命系统功能"""
    print("\n🧪 开始测试角色生命系统...")
    print("=" * 50)
    
    try:
        # 测试获取角色生命大纲
        role_id = "chenxiaozhi_001"
        outlines = await character_life_manager.get_life_plot_outlines_by_role(role_id)
        print(f"📋 角色 {role_id} 的生命大纲数量: {len(outlines)}")
        
        if outlines:
            outline = outlines[0]
            print(f"  大纲标题: {outline.title}")
            print(f"  角色生日: {outline.birthday}")
            print(f"  总体主题: {outline.overall_theme[:50]}...")
            
            # 测试获取生命阶段
            stages = await character_life_manager.get_life_stages_by_outline(outline.outline_id)
            print(f"  生命阶段数量: {len(stages)}")
            
            for stage in stages:
                print(f"    {stage.sequence_order}. {stage.title} ({stage.status.value})")
                
                # 测试获取剧情片段
                segments = await character_life_manager.get_plot_segments_by_stage(stage.life_stage_id)
                if segments:
                    print(f"      剧情片段数量: {len(segments)}")
                    for segment in segments:
                        print(f"        {segment.sequence_order_in_stage}. {segment.title} ({'里程碑' if segment.is_milestone_event else '普通'})")
                        
                        # 测试获取具体剧情
                        plots = await character_life_manager.get_specific_plots_by_segment(segment.plot_segment_id)
                        if plots:
                            print(f"          具体剧情数量: {len(plots)}")
                            for plot in plots:
                                print(f"            {plot.plot_order}. {plot.plot_date} ({plot.status.value})")
        
        print("✅ 角色生命系统测试完成")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        raise

async def main():
    """主函数"""
    await init_character_life_system()
    await test_character_life_system()

if __name__ == "__main__":
    asyncio.run(main()) 