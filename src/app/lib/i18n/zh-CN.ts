export const zhCN = {
  product: "CabinGuard 可信座舱协同智能体",
  productShort: "CabinGuard",
  mission: "任务驾驶舱",
  journey: "座舱交互",
  twin: "场景仿真",
  ops: "执行追溯",
  evaluation: "可靠性评测",
  architecture: "技术架构",
  caseStudy: "产品案例",
  agentLab: "旧版交互台",
  roles: {
    driver: "驾驶员",
    front_passenger: "前排乘客",
    rear_child: "后排儿童",
    guest: "访客",
  },
  risks: { low: "低风险", medium: "中风险", high: "高风险" },
  statuses: {
    pending: "待执行",
    running: "执行中",
    success: "已完成",
    blocked: "已阻止",
    skipped: "已跳过",
  },
} as const;

export type OccupantRole = keyof typeof zhCN.roles;
