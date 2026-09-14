export const zhCN = {
  product: "CabinGuard 可信座舱协同智能体",
  productShort: "CabinGuard",
  mission: "任务驾驶舱",
  journey: "旅程中控",
  twin: "数字孪生实验室",
  ops: "编排与证据中心",
  evaluation: "可靠性评测",
  architecture: "系统架构",
  caseStudy: "产品案例",
  agentLab: "经典 Agent 实验室",
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
