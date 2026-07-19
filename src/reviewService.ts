/**
 * reviewService.ts
 * Proactive review service for HephAIstus.
 * Analyzes schematics for potential issues and suggests improvements.
 */

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs/promises';
import { getReviewConfig, getPermissionLevel, PermissionLevel } from './configService';
import { loadState, saveState, ProjectState, checkPermission } from './stateManager';

// --- TYPE DEFINITIONS ---

export interface ReviewIssue {
    id: string;
    type: 'error' | 'warning' | 'suggestion' | 'info';
    category: 'connectivity' | 'values' | 'structure' | 'performance' | 'safety';
    message: string;
    location?: {
        file: string;
        line?: number;
        component?: string;
    };
    suggestion?: string;
    autoFixAvailable: boolean;
    permissionRequired: PermissionLevel;
}

export interface ReviewResult {
    timestamp: string;
    issues: ReviewIssue[];
    summary: {
        errors: number;
        warnings: number;
        suggestions: number;
        info: number;
    };
    permissionLevel: PermissionLevel;
    canAutoFix: boolean;
}

// --- REVIEW CATEGORIES ---

const REVIEW_CHECKS = {
    connectivity: {
        name: 'Connectivity',
        description: 'Check for unconnected pins, floating nets, missing connections'
    },
    values: {
        name: 'Values',
        description: 'Check for missing values, out-of-range values, inappropriate tolerances'
    },
    structure: {
        name: 'Structure',
        description: 'Check for design rule violations, placement issues'
    },
    performance: {
        name: 'Performance',
        description: 'Check for potential simulation issues, convergence problems'
    },
    safety: {
        name: 'Safety',
        description: 'Check for potential circuit damage, component stress'
    }
};

// --- REVIEW FUNCTIONS ---

/**
 * Generate a unique issue ID.
 */
function generateIssueId(): string {
    return `issue_${Date.now().toString(36)}_${Math.random().toString(36).substr(2, 5)}`;
}

/**
 * Run a comprehensive review on the project.
 */
export async function runReview(): Promise<ReviewResult> {
    const config = getReviewConfig();
    const permissionLevel = getPermissionLevel();
    
    console.log('[ReviewService] Starting proactive review...');
    
    const issues: ReviewIssue[] = [];
    
    // Load current state
    let state: ProjectState | null = null;
    try {
        state = await loadState();
    } catch (error) {
        issues.push({
            id: generateIssueId(),
            type: 'error',
            category: 'structure',
            message: 'Unable to load project state',
            autoFixAvailable: false,
            permissionRequired: 'values'
        });
    }
    
    // Run connectivity checks
    issues.push(...await runConnectivityChecks(state));
    
    // Run value checks
    issues.push(...await runValueChecks(state));
    
    // Run structure checks
    issues.push(...await runStructureChecks(state));
    
    // Run performance checks
    issues.push(...await runPerformanceChecks(state));
    
    // Run safety checks
    issues.push(...await runSafetyChecks(state));
    
    // Calculate summary
    const summary = {
        errors: issues.filter(i => i.type === 'error').length,
        warnings: issues.filter(i => i.type === 'warning').length,
        suggestions: issues.filter(i => i.type === 'suggestion').length,
        info: issues.filter(i => i.type === 'info').length
    };
    
    // Determine if auto-fix is possible
    const autoFixable = issues.filter(i => i.autoFixAvailable);
    const canAutoFix = autoFixable.every(i => 
        checkPermission(state || {} as ProjectState, 
            i.permissionRequired === 'restructure' ? 'rewire' : 
            i.permissionRequired === 'delete' ? 'deleteComponent' : 
            i.permissionRequired === 'add' ? 'addComponent' : 'modifyValue'
        ).allowed
    );
    
    const result: ReviewResult = {
        timestamp: new Date().toISOString(),
        issues,
        summary,
        permissionLevel,
        canAutoFix
    };
    
    console.log(`[ReviewService] Review complete: ${summary.errors} errors, ${summary.warnings} warnings`);
    
    return result;
}

/**
 * Run connectivity checks.
 */
async function runConnectivityChecks(state: ProjectState | null): Promise<ReviewIssue[]> {
    const issues: ReviewIssue[] = [];
    
    // TODO: Implement actual connectivity analysis
    // This would involve parsing KiCad files and checking for:
    // - Unconnected pins
    // - Floating nets
    // - Missing ground connections
    // - Missing power connections
    
    // Placeholder: Mock issues for demonstration
    if (state && state.files.kicad && state.files.kicad.length > 0) {
        // Simulate finding an unconnected pin
        if (Math.random() > 0.7) {
            issues.push({
                id: generateIssueId(),
                type: 'warning',
                category: 'connectivity',
                message: 'Potentially unconnected pin detected on U1',
                location: {
                    file: state.files.kicad[0],
                    component: 'U1'
                },
                suggestion: 'Connect pin to appropriate net or mark as no-connect',
                autoFixAvailable: false,
                permissionRequired: 'add'
            });
        }
    }
    
    return issues;
}

/**
 * Run value checks.
 */
async function runValueChecks(state: ProjectState | null): Promise<ReviewIssue[]> {
    const issues: ReviewIssue[] = [];
    
    // TODO: Implement actual value analysis
    // This would involve:
    // - Checking for missing component values
    // - Validating value ranges
    // - Checking tolerance specifications
    
    // Placeholder: Mock issues for demonstration
    if (state && Object.keys(state.stateHashes).length > 0) {
        // Simulate finding a missing value
        if (Math.random() > 0.8) {
            issues.push({
                id: generateIssueId(),
                type: 'error',
                category: 'values',
                message: 'Component R5 has no value specified',
                location: {
                    file: state.files.kicad?.[0] || '',
                    component: 'R5'
                },
                suggestion: 'Add value (e.g., 10k) to component properties',
                autoFixAvailable: true,
                permissionRequired: 'values'
            });
        }
    }
    
    return issues;
}

/**
 * Run structure checks.
 */
async function runStructureChecks(state: ProjectState | null): Promise<ReviewIssue[]> {
    const issues: ReviewIssue[] = [];
    
    // Check iteration status
    if (state && state.currentIteration >= state.maxIterations) {
        issues.push({
            id: generateIssueId(),
            type: 'warning',
            category: 'structure',
            message: `Maximum iterations reached (${state.maxIterations}). Consider creating a checkpoint.`,
            autoFixAvailable: false,
            permissionRequired: 'values'
        });
    }
    
    // Check for backup status
    if (state && !state.lastBackup) {
        issues.push({
            id: generateIssueId(),
            type: 'suggestion',
            category: 'structure',
            message: 'No backup has been created for this session',
            suggestion: 'Create a backup before making significant changes',
            autoFixAvailable: true,
            permissionRequired: 'values'
        });
    }
    
    return issues;
}

/**
 * Run performance checks.
 */
async function runPerformanceChecks(state: ProjectState | null): Promise<ReviewIssue[]> {
    const issues: ReviewIssue[] = [];
    
    // TODO: Implement performance analysis
    // This would involve:
    // - Checking for potential convergence issues in simulation
    // - Identifying high-component-count subcircuits
    // - Checking for appropriate simulation parameters
    
    return issues;
}

/**
 * Run safety checks.
 */
async function runSafetyChecks(state: ProjectState | null): Promise<ReviewIssue[]> {
    const issues: ReviewIssue[] = [];
    
    // TODO: Implement safety analysis
    // This would involve:
    // - Checking for potential component stress (power dissipation, voltage ratings)
    // - Identifying potential short circuits
    // - Checking for proper decoupling
    
    return issues;
}

/**
 * Format review results for display.
 */
export function formatReviewResult(result: ReviewResult): string {
    const lines: string[] = [];
    
    lines.push('# HephAIstus Review Results');
    lines.push(`**Timestamp:** ${result.timestamp}`);
    lines.push(`**Permission Level:** ${result.permissionLevel}`);
    lines.push('');
    
    // Summary
    lines.push('## Summary');
    lines.push(`- Errors: ${result.summary.errors}`);
    lines.push(`- Warnings: ${result.summary.warnings}`);
    lines.push(`- Suggestions: ${result.summary.suggestions}`);
    lines.push(`- Info: ${result.summary.info}`);
    lines.push('');
    
    if (result.canAutoFix) {
        lines.push('✅ Some issues can be auto-fixed at current permission level.');
    } else {
        lines.push('⚠️ Manual review required for some issues.');
    }
    lines.push('');
    
    // Group issues by type
    const byType = {
        error: result.issues.filter(i => i.type === 'error'),
        warning: result.issues.filter(i => i.type === 'warning'),
        suggestion: result.issues.filter(i => i.type === 'suggestion'),
        info: result.issues.filter(i => i.type === 'info')
    };
    
    for (const [type, issues] of Object.entries(byType)) {
        if (issues.length === 0) continue;
        
        const icon = type === 'error' ? '❌' : type === 'warning' ? '⚠️' : type === 'suggestion' ? '💡' : 'ℹ️';
        lines.push(`## ${icon.charAt(0).toUpperCase() + icon.slice(1)} ${type.charAt(0).toUpperCase() + type.slice(1)}s`);
        lines.push('');
        
        for (const issue of issues) {
            lines.push(`### ${issue.message}`);
            lines.push(`- **Category:** ${issue.category}`);
            lines.push(`- **Auto-fix:** ${issue.autoFixAvailable ? 'Available' : 'Not available'}`);
            if (issue.suggestion) {
                lines.push(`- **Suggestion:** ${issue.suggestion}`);
            }
            lines.push('');
        }
    }
    
    return lines.join('\n');
}

// --- VS CODE COMMAND REGISTRATION ---

/**
 * Register review-related commands with VS Code.
 */
export function registerReviewCommands(context: vscode.ExtensionContext): void {
    // Review Schematic command
    context.subscriptions.push(
        vscode.commands.registerCommand('hephaistus.reviewSchematic', async () => {
            const config = getReviewConfig();
            
            if (!config.onRequest) {
                vscode.window.showWarningMessage('On-request review is disabled in configuration.');
                return;
            }
            
            await vscode.window.withProgress(
                {
                    location: vscode.ProgressLocation.Notification,
                    title: 'Running HephAIstus Review...',
                    cancellable: false
                },
                async () => {
                    const result = await runReview();
                    const formatted = formatReviewResult(result);
                    
                    // Show results in a new document
                    const doc = await vscode.workspace.openTextDocument({
                        content: formatted,
                        language: 'markdown'
                    });
                    await vscode.window.showTextDocument(doc);
                }
            );
        })
    );
}

export default {
    runReview,
    formatReviewResult,
    registerReviewCommands
};