// 工具执行结果
export interface ToolResult {
  output: string;
  exitCode: number;
  timedOut?: boolean;
}

// 工具定义
export interface ToolDefinition {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
  execute(input: Record<string, unknown>): Promise<ToolResult>;
}
