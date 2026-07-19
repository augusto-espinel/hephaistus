#!/usr/bin/env node
/**
 * Post-install script for HephAIstus VS Code Extension
 *
 * This script runs after `npm install` to:
 * 1. Create the Python virtual environment
 * 2. Install Python dependencies
 */

const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const EXTENSION_NAME = 'hephaistus';
const PYTHON_PACKAGE_DIR = path.join(__dirname, '..', 'python');
const REQUIREMENTS_FILE = path.join(PYTHON_PACKAGE_DIR, 'requirements.txt');

console.log('=== HephAIstus Post-Install ===');

// Check if Python is available
function findPython() {
    const pythonCommands = ['python3', 'python'];
    for (const cmd of pythonCommands) {
        try {
            const version = execSync(`${cmd} --version`, { encoding: 'utf8' });
            console.log(`Found ${version.trim()}`);
            return cmd;
        } catch {
            continue;
        }
    }
    return null;
}

const python = findPython();
if (!python) {
    console.warn('⚠ Python not found. Python features will be disabled.');
    console.warn('  Install Python 3.9+ and run `npm run setup:python` manually.');
    process.exit(0); // Don't fail the install
}

// Check if requirements.txt exists
if (!fs.existsSync(REQUIREMENTS_FILE)) {
    console.warn('⚠ requirements.txt not found. Skipping Python setup.');
    process.exit(0);
}

// Create venv in extension global storage (done at runtime, not install time)
// This script just validates Python is available
console.log('✓ Python found. Extension will create venv on first activation.');
console.log('');
console.log('To manually set up Python environment:');
console.log('  npm run setup:python');
console.log('');