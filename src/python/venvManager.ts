/**
 * Virtual Environment Manager
 *
 * Creates and manages Python virtual environments for the extension.
 * Bootstraps dependencies on first run.
 */

import * as childProcess from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import * as vscode from 'vscode';

export interface VenvConfig {
    /** Extension global storage path */
    globalStoragePath: string;
    /** Python version to use */
    pythonVersion?: string;
    /** Requirements file path (relative to extension) */
    requirementsPath?: string;
}

export interface VenvStatus {
    /** Whether the venv exists */
    exists: boolean;
    /** Whether dependencies are installed */
    dependenciesInstalled: boolean;
    /** Path to the venv */
    venvPath: string;
    /** Path to Python executable */
    pythonPath: string;
    /** Path to pip executable */
    pipPath: string;
}

/**
 * Manages Python virtual environments for the HephAIstus extension.
 */
export class VenvManager {
    private config: VenvConfig;
    private venvPath: string;

    constructor(config: VenvConfig) {
        this.config = config;
        this.venvPath = path.join(config.globalStoragePath, 'hephaistus-venv');
    }

    /**
     * Check the status of the virtual environment.
     */
    async getStatus(): Promise<VenvStatus> {
        const pythonPath = this.getPythonPath();
        const pipPath = this.getPipPath();

        const exists = fs.existsSync(this.venvPath) && fs.existsSync(pythonPath);
        const dependenciesInstalled = exists && await this.checkDependencies();

        return {
            exists,
            dependenciesInstalled,
            venvPath: this.venvPath,
            pythonPath,
            pipPath,
        };
    }

    /**
     * Create the virtual environment if it doesn't exist.
     */
    async ensureVenv(): Promise<VenvStatus> {
        const status = await this.getStatus();

        if (!status.exists) {
            await this.createVenv();
        }

        if (!status.dependenciesInstalled) {
            await this.installDependencies();
        }

        return this.getStatus();
    }

    /**
     * Create a new virtual environment.
     */
    private async createVenv(): Promise<void> {
        const pythonVersion = this.config.pythonVersion || '3';
        const pythonBin = `python${pythonVersion}`;

        // Ensure global storage directory exists
        if (!fs.existsSync(this.config.globalStoragePath)) {
            fs.mkdirSync(this.config.globalStoragePath, { recursive: true });
        }

        return new Promise((resolve, reject) => {
            childProcess.exec(
                `${pythonBin} -m venv "${this.venvPath}"`,
                (error, stdout, stderr) => {
                    if (error) {
                        reject(new Error(`Failed to create venv: ${stderr || error.message}`));
                    } else {
                        resolve();
                    }
                }
            );
        });
    }

    /**
     * Install dependencies from requirements.txt.
     */
    private async installDependencies(): Promise<void> {
        const pipPath = this.getPipPath();
        const requirementsPath = this.config.requirementsPath || this.getDefaultRequirementsPath();

        if (!fs.existsSync(requirementsPath)) {
            throw new Error(`Requirements file not found: ${requirementsPath}`);
        }

        return new Promise((resolve, reject) => {
            childProcess.exec(
                `"${pipPath}" install -r "${requirementsPath}"`,
                { maxBuffer: 1024 * 1024 },
                (error, stdout, stderr) => {
                    if (error) {
                        reject(new Error(`Failed to install dependencies: ${stderr || error.message}`));
                    } else {
                        resolve();
                    }
                }
            );
        });
    }

    /**
     * Check if required dependencies are installed.
     */
    private async checkDependencies(): Promise<boolean> {
        const pipPath = this.getPipPath();

        return new Promise((resolve) => {
            childProcess.exec(
                `"${pipPath}" show kiutils skidl`,
                (error, stdout) => {
                    resolve(!error && stdout.includes('kiutils'));
                }
            );
        });
    }

    /**
     * Get the path to the Python executable in the venv.
     */
    private getPythonPath(): string {
        return path.join(this.venvPath, 'bin', 'python');
    }

    /**
     * Get the path to the pip executable in the venv.
     */
    private getPipPath(): string {
        return path.join(this.venvPath, 'bin', 'pip');
    }

    /**
     * Get the default requirements file path.
     */
    private getDefaultRequirementsPath(): string {
        // Assumes requirements.txt is bundled with the extension
        const extensionPath = vscode.extensions.getExtension('hephaistus.hephaistus')?.extensionPath;
        if (!extensionPath) {
            throw new Error('Could not determine extension path');
        }
        return path.join(extensionPath, 'python', 'requirements.txt');
    }
}

export default VenvManager;