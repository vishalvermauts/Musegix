"""Tests for PolyFabric Safe Context Pruner.

Verifies:
1. Target File Invariant: Active edit target file retains 100% bit-for-bit full content.
2. Background Files: Non-targeted background files are pruned to exported AST symbol signatures.
3. Real Token Measurements: True token/char counts computed without hardcoded constants.
4. Payload Pruning: Preserves <boltArtifact> and <boltAction> structure for bolt.diy WebContainer.
"""

import pytest
import re
from gateway.engines.polyfabric_pruner import PolyFabricPruner, count_tokens

APP_TSX_CONTENT = '''import React, { useState } from 'react';
import { Header } from './components/Header';
import { Button } from './components/Button';
import { UserService } from './services/UserService';

export default function App() {
  const [count, setCount] = useState<number>(0);
  const userService = new UserService('https://api.example.com');

  const handleIncrement = () => {
    setCount(prev => prev + 1);
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <Header title="Musegix Counter" />
      <div className="mt-4 flex items-center space-x-4">
        <span>Current Count: {count}</span>
        <Button onClick={handleIncrement}>Increment</Button>
      </div>
    </div>
  );
}'''

HEADER_TSX_CONTENT = '''import React from 'react';

export interface HeaderProps {
  title: string;
  subtitle?: string;
}

export function Header({ title, subtitle }: HeaderProps) {
  return (
    <header className="border-b border-gray-700 pb-4">
      <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
      {subtitle && <p className="text-gray-400 text-sm mt-1">{subtitle}</p>}
    </header>
  );
}'''

BUTTON_TSX_CONTENT = '''import React from 'react';

export interface ButtonProps {
  onClick: () => void;
  children: React.ReactNode;
  variant?: 'primary' | 'secondary' | 'danger';
}

export function Button({ onClick, children, variant = 'primary' }: ButtonProps) {
  const baseClasses = 'px-4 py-2 rounded-md font-medium transition-colors';
  const variantClasses = variant === 'primary' 
    ? 'bg-blue-600 hover:bg-blue-700 text-white' 
    : 'bg-gray-700 hover:bg-gray-600 text-gray-200';

  return (
    <button onClick={onClick} className={`${baseClasses} ${variantClasses}`}>
      {children}
    </button>
  );
}'''

USER_SERVICE_TS_CONTENT = '''import axios from 'axios';

export interface User {
  id: string;
  name: string;
  email: string;
  role: 'admin' | 'developer' | 'viewer';
}

export interface UserStats {
  loginCount: number;
  lastActive: string;
}

export class UserService {
  private apiUrl: string;
  private token: string | null = null;

  constructor(apiUrl: string) {
    this.apiUrl = apiUrl;
  }

  public setToken(token: string): void {
    this.token = token;
  }

  public async getUser(id: string): Promise<User> {
    const response = await axios.get(`${this.apiUrl}/users/${id}`, {
      headers: this.token ? { Authorization: `Bearer ${this.token}` } : {}
    });
    return response.data;
  }

  public async fetchStats(id: string): Promise<UserStats> {
    const response = await axios.get(`${this.apiUrl}/users/${id}/stats`);
    return response.data;
  }
}'''

HELPERS_PY_CONTENT = '''import os
from typing import List, Dict, Any

class DataProcessor:
    """Processes workspace telemetry and analytics."""

    def __init__(self, workspace_id: str):
        self.workspace_id = workspace_id
        self.cache: Dict[str, Any] = {}

    def process_records(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        total = sum(r.get("value", 0) for r in records)
        count = len(records)
        avg = total / count if count > 0 else 0.0
        return {"total": total, "count": count, "average": avg}

def format_summary(name: str, score: float) -> str:
    return f"Metric {name}: {score:.2f}"
'''

MULTI_FILE_BOLT_CONTEXT = f'''<boltArtifact id="project-files" title="Workspace Codebase">
<boltAction type="file" filePath="src/App.tsx">
{APP_TSX_CONTENT}
</boltAction>
<boltAction type="file" filePath="src/components/Header.tsx">
{HEADER_TSX_CONTENT}
</boltAction>
<boltAction type="file" filePath="src/components/Button.tsx">
{BUTTON_TSX_CONTENT}
</boltAction>
<boltAction type="file" filePath="src/services/UserService.ts">
{USER_SERVICE_TS_CONTENT}
</boltAction>
<boltAction type="file" filePath="scripts/helpers.py">
{HELPERS_PY_CONTENT}
</boltAction>
</boltArtifact>'''


def test_target_file_invariant_exact_preservation():
    """Verify Target File Invariant: The active target file is 100% intact."""
    pruner = PolyFabricPruner()
    target_file = "src/App.tsx"

    result = pruner.prune_context(
        context_text=MULTI_FILE_BOLT_CONTEXT,
        target_file=target_file,
    )

    # 1. Target file must be recorded in target_files and preserved_files
    assert target_file in result.target_files
    assert target_file in result.preserved_files

    # 2. Extract src/App.tsx from result.pruned_text
    match = re.search(
        r'<boltAction\s+[^>]*filePath=["\']src/App\.tsx["\'][^>]*>([\s\S]*?)</boltAction>',
        result.pruned_text,
    )
    assert match is not None, "src/App.tsx boltAction must exist in pruned output"
    extracted_body = match.group(1).strip()

    # 3. Target file body must be 100% byte-for-byte identical to the original
    assert extracted_body == APP_TSX_CONTENT.strip(), (
        "TARGET FILE INVARIANT VIOLATED: Active target file body was altered!"
    )


def test_background_files_pruned_to_ast_signatures():
    """Verify non-targeted background files are pruned to compact AST symbol signatures."""
    pruner = PolyFabricPruner()
    target_file = "src/App.tsx"

    result = pruner.prune_context(
        context_text=MULTI_FILE_BOLT_CONTEXT,
        target_file=target_file,
    )

    # Background files should be in pruned_files
    assert "src/components/Header.tsx" in result.pruned_files
    assert "src/components/Button.tsx" in result.pruned_files
    assert "src/services/UserService.ts" in result.pruned_files
    assert "scripts/helpers.py" in result.pruned_files

    # Check UserService.ts pruned content:
    user_service_match = re.search(
        r'<boltAction\s+[^>]*filePath=["\']src/services/UserService\.ts["\'][^>]*>([\s\S]*?)</boltAction>',
        result.pruned_text,
    )
    assert user_service_match is not None
    user_service_body = user_service_match.group(1)

    # Interfaces must be preserved
    assert "export interface User" in user_service_body
    assert "export interface UserStats" in user_service_body
    # Class signature must be preserved
    assert "class UserService" in user_service_body
    # Method signatures must be preserved
    assert "getUser" in user_service_body
    # Implementation details should NOT be present (pruned)
    assert "axios.get(`${this.apiUrl}/users/${id}`" not in user_service_body

    # Check Python helpers.py pruned content:
    py_match = re.search(
        r'<boltAction\s+[^>]*filePath=["\']scripts/helpers\.py["\'][^>]*>([\s\S]*?)</boltAction>',
        result.pruned_text,
    )
    assert py_match is not None
    py_body = py_match.group(1)
    assert "class DataProcessor" in py_body
    assert "def process_records" in py_body
    assert "total = sum(r.get" not in py_body  # body was stubbed


def test_token_measurements_are_honest_and_not_hardcoded():
    """Verify token measurements are measured dynamically without hardcoded constants."""
    pruner = PolyFabricPruner()

    result = pruner.prune_context(
        context_text=MULTI_FILE_BOLT_CONTEXT,
        target_file="src/App.tsx",
    )

    # Verify real counts
    assert result.raw_tokens > 0
    assert result.pruned_tokens > 0
    assert result.raw_tokens > result.pruned_tokens
    assert result.saved_tokens == result.raw_tokens - result.pruned_tokens

    # Expected exact formula: round((1 - pruned/raw) * 100, 2)
    expected_pct = round((1.0 - (result.pruned_tokens / result.raw_tokens)) * 100.0, 2)
    assert result.reduction_pct == expected_pct

    # Crucial check: verify that reduction_pct is NOT the fake constants 90.8 or 85.0
    # and not derived from * 0.14
    assert result.reduction_pct > 10.0
    assert result.pruned_tokens != int(result.raw_tokens * 0.14)

    # Test with a single small file: reduction should be 0% when only target exists
    single_file_context = f'<boltAction type="file" filePath="src/App.tsx">\n{APP_TSX_CONTENT}\n</boltAction>'
    single_res = pruner.prune_context(single_file_context, target_file="src/App.tsx")
    assert single_res.reduction_pct == 0.0
    assert single_res.saved_tokens == 0


def test_auto_detection_of_target_file_from_user_prompt():
    """Verify target file is automatically detected from the user prompt text."""
    pruner = PolyFabricPruner()

    prompt = "Please update src/components/Button.tsx to add an icon prop and style it."
    result = pruner.prune_context(
        context_text=MULTI_FILE_BOLT_CONTEXT,
        user_prompt=prompt,
    )

    # Button.tsx must be recognized as the target and preserved 100%
    assert "src/components/Button.tsx" in result.target_files
    assert "src/components/Button.tsx" in result.preserved_files

    button_match = re.search(
        r'<boltAction\s+[^>]*filePath=["\']src/components/Button\.tsx["\'][^>]*>([\s\S]*?)</boltAction>',
        result.pruned_text,
    )
    assert button_match is not None
    assert button_match.group(1).strip() == BUTTON_TSX_CONTENT.strip()

    # Other files must be pruned
    assert "src/App.tsx" in result.pruned_files
    assert "src/services/UserService.ts" in result.pruned_files


def test_prune_payload_openai_format():
    """Verify payload pruning handles OpenAI chat completions payload structure."""
    pruner = PolyFabricPruner()

    payload = {
        "model": "musecontext-auto",
        "messages": [
            {
                "role": "system",
                "content": f"You are an assistant. Here is the codebase:\n{MULTI_FILE_BOLT_CONTEXT}"
            },
            {
                "role": "user",
                "content": "Add a new endpoint call inside src/services/UserService.ts"
            }
        ]
    }

    new_payload, res = pruner.prune_payload(payload)

    # Target file in UserService.ts should be preserved
    assert "src/services/UserService.ts" in res.target_files
    assert "src/services/UserService.ts" in res.preserved_files

    # Pruned payload system message must retain UserService.ts full body
    sys_content = new_payload["messages"][0]["content"]
    assert "axios.get(`${this.apiUrl}/users/${id}`" in sys_content
    # App.tsx should have been pruned in background
    assert "src/App.tsx" in res.pruned_files
    assert res.raw_tokens > res.pruned_tokens
    assert res.reduction_pct > 0.0
