/**
 * Simulation Runner Service
 *
 * Orchestrates SPICE simulations via Python bridge.
 * Supports SKiDL schematic generation and ngspice simulation.
 */

import { PythonBridge } from './pythonBridge';
import { VenvManager } from './venvManager';
import * as path from 'path';

export interface SimulationConfig {
    /** Path to the circuit file (Python or netlist) */
    circuitPath: string;
    /** Simulation type (ac, dc, transient, etc.) */
    simType: 'ac' | 'dc' | 'transient' | 'noise' | 'spice';
    /** Simulation parameters */
    params?: Record<string, unknown>;
    /** Output format */
    outputFormat?: 'json' | 'raw' | 'csv';
}

export interface SimulationResult {
    /** Whether the simulation succeeded */
    success: boolean;
    /** Simulation output data */
    data?: Record<string, unknown>;
    /** Error message if failed */
    error?: string;
    /** Execution time in milliseconds */
    executionTime: number;
}

/**
 * Runs SPICE simulations via Python bridge.
 */
export class SimulationRunner {
    private bridge: PythonBridge;
    private venvManager: VenvManager;
    private venvPath: string;

    constructor(venvManager: VenvManager) {
        this.venvManager = venvManager;
        this.venvPath = '';
        this.bridge = new PythonBridge();
    }

    /**
     * Initialize the bridge with the venv path (call after construction).
     */
    async initialize(): Promise<void> {
        const status = await this.venvManager.getStatus();
        this.venvPath = status.venvPath;
        this.bridge = new PythonBridge(this.venvPath);
    }

    /**
     * Run a SPICE simulation.
     */
    async runSimulation(config: SimulationConfig): Promise<SimulationResult> {
        const status = await this.venvManager.getStatus();

        if (!status.exists || !status.dependenciesInstalled) {
            return {
                success: false,
                error: 'Python virtual environment not ready. Please run setup.',
                executionTime: 0,
            };
        }

        const startTime = Date.now();

        try {
            // TODO: Implement actual simulation runner
            // This is a stub that will be implemented when the simulation module is ready
            const scriptPath = this.getSimulationScript();
            const args = [
                '--circuit', config.circuitPath,
                '--type', config.simType,
                '--format', config.outputFormat || 'json',
            ];

            if (config.params) {
                args.push('--params', JSON.stringify(config.params));
            }

            const result = await this.bridge.execute(scriptPath, args);

            const executionTime = Date.now() - startTime;

            if (result.success) {
                return {
                    success: true,
                    data: typeof result.stdout === 'string'
                        ? JSON.parse(result.stdout)
                        : result.stdout,
                    executionTime,
                };
            } else {
                return {
                    success: false,
                    error: result.stderr,
                    executionTime,
                };
            }
        } catch (err) {
            return {
                success: false,
                error: err instanceof Error ? err.message : String(err),
                executionTime: Date.now() - startTime,
            };
        }
    }

    /**
     * Generate a netlist from SKiDL code.
     */
    async generateNetlist(pythonPath: string): Promise<string> {
        // TODO: Implement SKiDL netlist generation
        throw new Error('SKiDL netlist generation not yet implemented');
    }

    /**
     * Get the path to the simulation runner script.
     */
    private getSimulationScript(): string {
        // Path to the Python simulation runner
        return path.join(
            __dirname,
            '..',
            '..',
            'python',
            'hephaistus',
            'simulation',
            'ngspice_runner.py'
        );
    }
}

export default SimulationRunner;