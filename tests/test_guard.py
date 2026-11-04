"""Tests for Veylqora Evidence-Anchored Memory Guard.

Verifies:
1. SQLite WAL Mode: Verifies the SQLite database operates in Write-Ahead Logging mode.
2. Symbol-Anchored Staleness: Flags SUSPECTED_STALE only when cited files or AST symbols mutate.
3. Chat/Session Isolation: Verifies strict state isolation per chat/session.
4. Payload Inspection: Correctly extracts boltAction files and identifies mutations across turns.
"""

import os
import pytest
import tempfile
from gateway.engines.veylqora_guard import VeylqoraGuard, sha256_text

INITIAL_HEADER = '''import React from 'react';
export interface HeaderProps {
  title: string;
}
export function Header({ title }: HeaderProps) {
  return <h1>{title}</h1>;
}
'''

MODIFIED_HEADER = '''import React from 'react';
export interface HeaderProps {
  title: string;
  theme?: 'dark' | 'light';
}
export function Header({ title, theme = 'dark' }: HeaderProps) {
  return <h1 className={theme}>{title}</h1>;
}
'''

INITIAL_BUTTON = '''import React from 'react';
export function Button({ label }: { label: string }) {
  return <button>{label}</button>;
}
'''

INITIAL_USER_SERVICE = '''export class UserService {
  getUser(id: string) {
    return { id, name: 'Alice' };
  }
}
'''

MODIFIED_USER_SERVICE = '''export class UserService {
  getUser(id: string) {
    return { id, name: 'Alice Updated', role: 'admin' };
  }
}
'''


@pytest.fixture
def temp_guard(tmp_path):
    """Fixture providing a VeylqoraGuard instance backed by a temporary SQLite database."""
    db_file = tmp_path / "veylqora_test.db"
    guard = VeylqoraGuard(db_path=str(db_file))
    return guard


def test_sqlite_wal_mode_enabled(temp_guard):
    """Verify that SQLite database runs in Write-Ahead Logging (WAL) mode."""
    mode = temp_guard.get_journal_mode()
    assert mode == "wal", f"Expected SQLite journal mode 'wal', got '{mode}'"


def test_initial_turn_is_active_zero_stale(temp_guard):
    """Verify that Turn 0 / baseline registration has status ACTIVE and 0 stale symbols."""
    session_id = "test_chat_001"
    files = {
        "src/components/Header.tsx": INITIAL_HEADER,
        "src/components/Button.tsx": INITIAL_BUTTON,
    }

    report = temp_guard.inspect_turn(session_id=session_id, files=files)

    assert report.status == "ACTIVE"
    assert report.stale_count == 0
    assert len(report.mutated_symbols) == 0
    assert report.total_symbols_tracked > 0
    assert report.session_id == session_id
    assert "ACTIVE" in report.banner_text()


def test_subsequent_turn_identical_files_remains_active(temp_guard):
    """Verify that identical files between turns do not trigger false positive staleness."""
    session_id = "test_chat_002"
    files = {
        "src/components/Header.tsx": INITIAL_HEADER,
        "src/components/Button.tsx": INITIAL_BUTTON,
    }

    # Turn 1
    temp_guard.inspect_turn(session_id=session_id, files=files)

    # Turn 2 with identical files
    report_2 = temp_guard.inspect_turn(session_id=session_id, files=files)

    assert report_2.status == "ACTIVE"
    assert report_2.stale_count == 0
    assert len(report_2.mutated_symbols) == 0


def test_mutation_flags_suspected_stale_with_symbol_details(temp_guard):
    """Verify that modifying a previously seen symbol triggers SUSPECTED_STALE with exact details."""
    session_id = "test_chat_003"
    files_turn_1 = {
        "src/components/Header.tsx": INITIAL_HEADER,
        "src/components/Button.tsx": INITIAL_BUTTON,
    }

    # Turn 1: register baseline
    temp_guard.inspect_turn(session_id=session_id, files=files_turn_1)

    # Turn 2: Header.tsx is modified, Button.tsx remains unchanged
    files_turn_2 = {
        "src/components/Header.tsx": MODIFIED_HEADER,
        "src/components/Button.tsx": INITIAL_BUTTON,
    }

    report_2 = temp_guard.inspect_turn(session_id=session_id, files=files_turn_2)

    assert report_2.status == "SUSPECTED_STALE"
    assert report_2.stale_count > 0
    assert "SUSPECTED_STALE" in report_2.banner_text()

    # Verify that the mutated symbol correctly points to Header.tsx
    mutated_files = [m.file_path for m in report_2.mutated_symbols]
    assert "src/components/Header.tsx" in mutated_files
    assert "src/components/Button.tsx" not in mutated_files, "Unchanged Button.tsx should not be mutated"

    # Verify that mutated symbol has different old_hash and new_hash
    header_mut = next(m for m in report_2.mutated_symbols if m.file_path == "src/components/Header.tsx")
    assert header_mut.old_hash != header_mut.new_hash
    assert len(header_mut.old_hash) == 64
    assert len(header_mut.new_hash) == 64


def test_session_isolation_prevents_cross_chat_contamination(temp_guard):
    """Verify that mutations in session A NEVER affect session B."""
    session_a = "chat_alpha_123"
    session_b = "chat_beta_456"

    initial_files = {
        "src/services/UserService.ts": INITIAL_USER_SERVICE,
    }

    # Register both sessions at Turn 1 with identical initial files
    report_a1 = temp_guard.inspect_turn(session_id=session_a, files=initial_files)
    report_b1 = temp_guard.inspect_turn(session_id=session_b, files=initial_files)

    assert report_a1.status == "ACTIVE"
    assert report_b1.status == "ACTIVE"

    # Mutate UserService in session_a ONLY
    modified_files = {
        "src/services/UserService.ts": MODIFIED_USER_SERVICE,
    }
    report_a2 = temp_guard.inspect_turn(session_id=session_a, files=modified_files)

    # Session A must be SUSPECTED_STALE
    assert report_a2.status == "SUSPECTED_STALE"
    assert report_a2.stale_count > 0

    # Session B sends its unchanged files: must remain ACTIVE!
    report_b2 = temp_guard.inspect_turn(session_id=session_b, files=initial_files)
    assert report_b2.status == "ACTIVE", "Cross-chat contamination: session B was affected by session A!"
    assert report_b2.stale_count == 0


def test_payload_inspection_and_session_derivation(temp_guard):
    """Verify inspect_payload extracts files from boltAction and isolates derived session."""
    payload_turn_1 = {
        "messages": [
            {
                "role": "user",
                "content": f"""Project context:
<boltArtifact id="art-1" title="App">
<boltAction type="file" filePath="src/components/Header.tsx">
{INITIAL_HEADER}
</boltAction>
</boltArtifact>
Make a header component.
"""
            }
        ]
    }

    report_1 = temp_guard.inspect_payload(payload_turn_1)
    assert report_1.status == "ACTIVE"
    assert report_1.stale_count == 0

    # Turn 2: modified payload
    payload_turn_2 = {
        "messages": [
            {
                "role": "user",
                "content": f"""Project context:
<boltArtifact id="art-1" title="App">
<boltAction type="file" filePath="src/components/Header.tsx">
{MODIFIED_HEADER}
</boltAction>
</boltArtifact>
Update header with theme.
"""
            }
        ]
    }

    # Using the same session_id
    report_2 = temp_guard.inspect_payload(payload_turn_2, session_id=report_1.session_id)
    assert report_2.status == "SUSPECTED_STALE"
    assert report_2.stale_count > 0
