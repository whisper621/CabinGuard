import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Keep one-click demo runs from generating untracked agent instruction files.
  agentRules: false,
};

export default nextConfig;
