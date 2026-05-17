import { describe, test, expect } from 'bun:test';
import { execCommand } from '../../src/utils/shell';

describe('execCommand', () => {
  test('local backend - 执行简单命令', async () => {
    const result = await execCommand('echo hello', { type: 'local' });
    expect(result.stdout).toBe('hello');
    expect(result.exitCode).toBe(0);
    expect(result.timedOut).toBe(false);
  });

  test('local backend - 捕获 exit code', async () => {
    const result = await execCommand('exit 42', { type: 'local' });
    expect(result.exitCode).toBe(42);
  });

  test('local backend - 超时处理', async () => {
    const result = await execCommand('ping -n 10 127.0.0.1', { type: 'local' }, { timeout: 1000 });
    expect(result.timedOut).toBe(true);
  }, 15000);

  test('local backend - 捕获 stderr', async () => {
    const result = await execCommand('echo err >&2', { type: 'local' });
    expect(result.stdout).toBe('err');
    expect(result.exitCode).toBe(0);
  });
});
