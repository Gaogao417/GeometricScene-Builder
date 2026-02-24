import { spawn, spawnSync } from "node:child_process";
import path from "node:path";
import { tool } from "@opencode-ai/plugin";

function safeResolve(worktree: string, inputPath: string): string {
  const abs = path.resolve(worktree, inputPath);
  if (!abs.startsWith(worktree)) {
    throw new Error(`path escapes workspace: ${inputPath}`);
  }
  return abs;
}

function runPython(worktree: string, scriptRel: string, args: string[]): string {
  const scriptAbs = safeResolve(worktree, scriptRel);
  const proc = spawnSync("python", [scriptAbs, ...args], {
    cwd: worktree,
    encoding: "utf-8",
  });
  if (proc.status !== 0) {
    return JSON.stringify(
      {
        status: "error",
        message: proc.stderr || proc.stdout || "command failed",
        exit_code: proc.status,
      },
      null,
      2,
    );
  }
  return proc.stdout.trim() || JSON.stringify({ status: "ok" });
}

export const GeoToolsPlugin = async () => {
  return {
    tool: {
      run_sweep: tool({
        description: "Run geometry benchmark sweep from config path",
        args: {
          config_path: tool.schema.string().describe("sweep yaml path"),
          out_dir: tool.schema.string().optional().describe("output run dir"),
          problems_path: tool.schema.string().optional().describe("problems jsonl path"),
        },
        async execute(args, context) {
          const config = safeResolve(context.worktree, args.config_path);
          const problems = safeResolve(context.worktree, args.problems_path ?? "data/problems.jsonl");
          const toolArgs = ["--config", config, "--problems", problems];
          if (args.out_dir) {
            toolArgs.push("--out", safeResolve(context.worktree, args.out_dir));
          }
          return runPython(context.worktree, "scripts/bench.py", toolArgs);
        },
      }),
      build_report: tool({
        description: "Build report.md, report.html and analysis_report.html",
        args: {
          run_dir: tool.schema.string().describe("run directory path"),
        },
        async execute(args, context) {
          const runDir = safeResolve(context.worktree, args.run_dir);
          const reportOut = runPython(context.worktree, "scripts/report.py", ["--run_dir", runDir]);
          const analysisOut = runPython(context.worktree, "scripts/analyze.py", ["--run_dir", runDir]);
          // Parse the JSON outputs from scripts to avoid double-stringifying
          const reportParsed = JSON.parse(reportOut);
          const analysisParsed = JSON.parse(analysisOut);
          return JSON.stringify(
            {
              status: "ok",
              report: reportParsed,
              analysis: analysisParsed,
            },
            null,
            2,
          );
        },
      }),
      launch_rater: tool({
        description: "Launch streamlit scoring UI for a run directory",
        args: {
          run_dir: tool.schema.string().describe("run directory path"),
        },
        async execute(args, context) {
          const runDir = safeResolve(context.worktree, args.run_dir);
          const child = spawn(
            "streamlit",
            ["run", safeResolve(context.worktree, "app/rate_streamlit.py"), "--", "--run_dir", runDir],
            { cwd: context.worktree, detached: true, stdio: "ignore" },
          );
          child.unref();
          return JSON.stringify({ status: "ok", ui: "started", run_dir: runDir }, null, 2);
        },
      }),
    },
  };
};
