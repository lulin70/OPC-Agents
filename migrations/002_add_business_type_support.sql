-- ============================================================
-- OPC-Agents V2.1 数据库迁移脚本
-- 版本: 002_add_business_type_support.sql
-- 日期: 2026-04-15
-- 作者: 架构师团队
-- 描述: 添加业务类型支持、场景执行追踪、飞轮状态管理
-- ============================================================

-- ============================================================
-- 1. 用户业务类型表 (user_business_types)
-- 用途：记录用户所属的业务类型（支持多类型）
-- ============================================================
CREATE TABLE IF NOT EXISTS user_business_types (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    business_type VARCHAR(32) NOT NULL,  -- 对应 BusinessType 枚举值
    is_primary BOOLEAN DEFAULT FALSE,   -- 是否为主类型
    confidence_score FLOAT DEFAULT 0.0, -- 检测置信度（0.0-1.0）
    detection_method VARCHAR(32),       -- 检测方法: keyword_match/profile_inference/history_analysis/manual
    detected_at TIMESTAMP DEFAULT NOW(),
    confirmed_at TIMESTAMP,             -- 用户确认时间（NULL表示未确认）
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- 约束：每个用户的每种类型唯一
    UNIQUE(user_id, business_type),

    -- 索引：快速查询用户的所有类型
    INDEX idx_ubt_user_id (user_id),
    -- 索引：按类型查询用户
    INDEX idx_ubt_business_type (business_type),
    -- 索引：查找主类型
    INDEX idx_ubt_is_primary (is_primary) WHERE is_primary = TRUE
);

-- 注释
COMMENT ON TABLE user_business_types IS '用户业务类型映射表 - 支持一人公司6大类型';
COMMENT ON COLUMN user_business_types.business_type IS '业务类型: content_creator/digital_product/ai_tool_builder/consultant/ecommerce/creative_work';
COMMENT ON COLUMN user_business_types.confidence_score IS '检测置信度，越高表示越确定';
COMMENT ON COLUMN user_business_types.detection_method IS '检测方法: keyword_match(关键词匹配)/profile_inference(档案推断)/history_analysis(历史分析)/manual(手动设置)';


-- ============================================================
-- 2. 场景执行记录扩展 (task_executions 表 ALTER)
-- 用途：在现有任务执行记录中增加V2.1的字段
-- ============================================================

-- 检查列是否存在，不存在则添加
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'task_executions'
        AND column_name = 'business_type'
    ) THEN
        ALTER TABLE task_executions
        ADD COLUMN business_type VARCHAR(32);

        COMMENT ON COLUMN task_executions.business_type IS 'V2.1新增 - 业务类型标识';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'task_executions'
        AND column_name = 'scenario_id'
    ) THEN
        ALTER TABLE task_executions
        ADD COLUMN scenario_id VARCHAR(64);

        COMMENT ON COLUMN task_executions.scenario_id IS 'V2.1新增 - 场景ID（如 content_calendar, launch_product 等）';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'task_executions'
        AND column_name = 'persona_variant'
    ) THEN
        ALTER TABLE task_executions
        ADD COLUMN persona_variant VARCHAR(32);

        COMMENT ON COLUMN task_executions.persona_variant IS 'V2.1新增 - 使用的人格变体ID';
    END IF;
END $$;

-- 为新字段创建索引（如果需要频繁查询）
CREATE INDEX IF NOT EXISTS idx_te_business_type ON task_executions(business_type);
CREATE INDEX IF NOT EXISTS idx_te_scenario_id ON task_executions(scenario_id);


-- ============================================================
-- 3. 飞轮状态追踪表 (user_flywheel_status)
-- 用途：跟踪用户的"混合生态飞轮"成长阶段
-- ============================================================
CREATE TABLE IF NOT EXISTS user_flywheel_status (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL UNIQUE,

    -- 当前飞轮等级
    current_level INT DEFAULT 1,  -- 1=单一类型, 2=双类型组合, 3=全生态

    -- 已激活的业务类型列表（JSON数组）
    active_types JSONB DEFAULT '[]',

    -- 飞轮健康度评分（0.0-100.0）
    flywheel_health_score FLOAT DEFAULT 0.0,

    -- 各维度得分明细（JSON对象）
    dimension_scores JSONB DEFAULT '{}',
    -- 结构示例:
    -- {
    --   "content_quality": 85.0,
    --   "audience_growth": 72.0,
    --   "monetization": 60.0,
    --   "cross_promotion": 45.0,
    --   "ecosystem_synergy": 30.0
    -- }

    -- 最后一次等级转换的时间
    last_transition_date TIMESTAMP,

    -- 统计数据（JSON对象）
    stats JSONB DEFAULT '{}',
    -- 结构示例:
    -- {
    --   "total_scenarios_completed": 25,
    --   "active_days_count": 15,
    --   "types_explored": 2,
    --   "last_activity_date": "2026-04-15"
    -- }

    -- 元数据（扩展字段）
    metadata JSONB DEFAULT '{}',

    -- 时间戳
    updated_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 注释
COMMENT ON TABLE user_flywheel_status IS '用户飞轮状态追踪表 - 记录混合生态成长路径';
COMMENT ON COLUMN user_flywheel_status.current_level IS '飞轮等级: 1(单一类型) / 2(双类型组合) / 3(全生态系统)';
COMMENT ON COLUMN user_flywheel_status.active_types IS '已激活的业务类型JSON数组';
COMMENT ON COLUMN user_flywheel_status.flywheel_health_score IS '整体健康度评分 (0-100)';
COMMENT ON COLUMN user_flywheel_status.dimension_scores IS '各维度得分详情JSON';
COMMENT ON COLUMN user_flywheel_status.last_transition_date IS '最后一次等级跃升时间';


-- ============================================================
-- 4. 初始化数据（可选）
-- 为现有用户设置默认值
-- ============================================================

-- 注意：以下语句需要根据实际情况取消注释执行
-- INSERT INTO user_flywheel_status (user_id, current_level, active_types, flywheel_health_score)
-- SELECT DISTINCT user_id, 1, '["content_creator"]'::jsonb, 50.0
-- FROM users
-- WHERE NOT EXISTS (SELECT 1 FROM user_flywheel_status WHERE user_flywheel_status.user_id = users.user_id);


-- ============================================================
-- 5. 验证脚本（用于测试迁移是否成功）
-- ============================================================

-- 验证表是否创建成功
SELECT
    'user_business_types' AS table_name,
    COUNT(*) AS column_count
FROM information_schema.columns
WHERE table_name = 'user_business_types'

UNION ALL

SELECT
    'user_flywheel_status' AS table_name,
    COUNT(*) AS column_count
FROM information_schema.columns
WHERE table_name = 'user_flywheel_status'

UNION ALL

SELECT
    'task_executions (new columns)' AS info,
    COUNT(*) AS new_columns_added
FROM information_schema.columns
WHERE table_name = 'task_executions'
AND column_name IN ('business_type', 'scenario_id', 'persona_variant');


-- ============================================================
-- 迁移完成提示
-- ============================================================
-- DO $$
-- BEGIN
--     RAISE NOTICE '✅ OPC-Agents V2.1 数据库迁移完成！';
--     RAISE NOTICE '新增表: user_business_types, user_flywheel_status';
--     RAISE NOTICE '扩展表: task_executions (+3 columns)';
--     END $$;
-- ============================================================
