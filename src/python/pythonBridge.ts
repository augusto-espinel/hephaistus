/**
 * Python Bridge Service
 *
 * Spawns Python processes from the VS Code extension.
 * Handles process lifecycle, error handling, and result parsing.
 */

import * as childProcess from 'child_process';
import * as path from 'path';

export interface PythonBridgeOptions {
    /** Path to Python executable (defaults to venv python) */
    pythonPath?: string;
    /** Working directory for the Python process */
    cwd?: string;
    /** Environment variables to pass to Python */
    env?: NodeJS.ProcessEnv;
    /** Timeout in milliseconds */
    timeout?: number;
}

export interface PythonResult {
    /** Exit code from Python process */
    exitCode: number;
    /** Standard output (parsed as JSON if possible) */
    stdout: string | object;
    /** Standard error output */
    stderr: string;
    /** Whether the process completed successfully */
    success: boolean;
}

/**
 * Python Bridge class for executing Python scripts from TypeScript.
 */
export class PythonBridge {
    private defaultPythonPath: string;

    constructor(venvPath?: string) {
        // Default to venv python if available
        this.defaultPythonPath = venvPath
            ? path.join(venvPath, 'bin', 'python')
            : 'python3';
    }

    /**
     * Execute a Python script and return the result.
     */
    async execute(
        scriptPath: string,
        args: string[] = [],
        options: PythonBridgeOptions = {}
    ): Promise<PythonResult> {
        const pythonPath = options.pythonPath || this.defaultPythonPath;
        const cwd = options.cwd || process.cwd();

        return new Promise((resolve, reject) => {
            const proc = childProcess.spawn(pythonPath, [scriptPath, ...args], {
                cwd,
                env: { ...process.env, ...options.env },
            });

            let stdout = '';
            let stderr = '';

            proc.stdout.on('data', (data) => {
                stdout += data.toString();
            });

            proc.stderr.on('data', (data) => {
                stderr += data.toString();
            });

            // Handle timeout
            const timeout = options.timeout || 60000;
            const timeoutId = setTimeout(() => {
                proc.kill();
                reject(new Error(`Python process timed out after ${timeout}ms`));
            }, timeout);

            proc.on('close', (exitCode) => {
                clearTimeout(timeoutId);

                // Try to parse stdout as JSON
                let parsedStdout: string | object = stdout;
                try {
                    parsedStdout = JSON.parse(stdout);
                } catch {
                    // Keep as string if not valid JSON
                }

                resolve({
                    exitCode: exitCode ?? 1,
                    stdout: parsedStdout,
                    stderr,
                    success: exitCode === 0,
                });
            });

            proc.on('error', (err) => {
                clearTimeout(timeoutId);
                reject(err);
            });
        });
    }

    /**
     * Execute a Python module function directly.
     */
    async executeModule(
        moduleName: string,
        functionName: string,
        args: unknown[] = [],
        options: PythonBridgeOptions = {}
    ): Promise<PythonResult> {
        const script = `
import json
import sys
from ${moduleName} import ${functionName}

args = json.loads(sys.argv[1]) if sys.argv[1] else []
result = ${functionName}(*args)
print(json.dumps(result))
        `;

        // Write script to temp file and execute
        // TODO: Implement temp file approach
        throw new Error('executeModule not yet implemented');
    }
}

export default PythonBridge;