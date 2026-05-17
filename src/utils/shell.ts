import { ExecBackend } from '../types/config';

export interface ShellResult {
  stdout: string;
  exitCode: number;
  timedOut: boolean;
}

function buildSpawnArgs(command: string, backend: ExecBackend): { cmd: string[]; env?: Record<string, string> } {
  switch (backend.type) {
    case 'local':
      if (process.platform === 'win32') {
        return { cmd: ['cmd.exe', '/C', command] };
      }
      return { cmd: ['bash', '-c', command] };
    case 'wsl':
      return { cmd: ['wsl', '-d', backend.distro, '--', 'bash', '-c', command] };
    case 'ssh': {
      const sshArgs: string[] = ['ssh'];
      if (backend.port !== 22) sshArgs.push('-p', String(backend.port));
      if (backend.authMethod === 'key' && backend.keyFile) {
        sshArgs.push('-i', backend.keyFile);
      }
      sshArgs.push('-o', 'StrictHostKeyChecking=no');
      sshArgs.push(`${backend.user}@${backend.host}`, command);
      return { cmd: sshArgs };
    }
    case 'docker':
      return { cmd: ['docker', 'exec', backend.container, 'bash', '-c', command] };
  }
}

export async function execCommand(
  command: string,
  backend: ExecBackend,
  options: { timeout?: number; cwd?: string } = {}
): Promise<ShellResult> {
  const { timeout = 120000, cwd } = options;
  const { cmd } = buildSpawnArgs(command, backend);

  const proc = Bun.spawn(cmd, {
    cwd: backend.type === 'local' ? cwd : undefined,
    stdout: 'pipe',
    stderr: 'pipe',
  });

  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    proc.kill();
  }, timeout);

  const [stdoutBuf, stderrBuf] = await Promise.all([
    new Response(proc.stdout).text(),
    new Response(proc.stderr).text(),
  ]);
  const exitCode = await proc.exited;
  clearTimeout(timer);

  const output = (stdoutBuf + stderrBuf).trimEnd();

  return { stdout: output, exitCode, timedOut };
}
