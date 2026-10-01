#!/usr/bin/env python3
"""PreToolUse(Bash) 실행 전 알림. 기본은 차단하지 않고 컨텍스트만 준다.

예외: 시한 없는 백그라운드 대기 루프(until/while)는 거절한다. 본 대화의 백그라운드 명령은 턴이 끝나도
계속 돌고(공식 문서 tools-reference 「Background commands」), 앱이 그 작업을 살아 있다고 보고 방 보관을 막는다
(2026-09-27 스마트플레이스 방, 9/26 21:32 until curl 루프 2개).

Claude Code 훅은 stdin으로 이벤트 JSON을 받는다 (`$TOOL_INPUT` 환경변수는 없다).
"""
import json
import os
import re
import sys

LONG_RUNNING = re.compile(
    r'^\s*(python3?|pip3?|npm|yarn|pnpm|cargo|pytest|expect|node\s+build)\b')
PUSH = re.compile(r'\bpush\b')
WAIT_LOOP = re.compile(r'\b(until|while)\b[^\n]*?[;\n]\s*do\b', re.S)
# timeout N, SECONDS 경과 비교, 횟수 비교(-lt/-le/-ge/-gt) 중 하나가 있으면 끝나는 조건이 있다고 본다.
BOUNDED = re.compile(r'\btimeout\s+\d|\bSECONDS\b|-(lt|le|ge|gt)\b')
UNBOUNDED_MSG = ('시한 없는 백그라운드 대기 루프는 막습니다. 끝나지 않으면 대화가 끝나도 계속 돌고 방 보관도 막힙니다. '
                 '`timeout 900 bash -c \'until ...; do sleep 5; done\'`처럼 시한을 두거나, Monitor 도구의 timeout_ms를 쓰세요.')


# 셸 좌표 클릭은 화면을 안 보고 좌표를 추측하게 된다(rules/screen-verification.md). 부팅·설치·로그 조회는 통과.
# 명령 위치(줄 앞·구분자 뒤·래퍼 뒤)만 본다. grep 인자 속 단어를 잡던 오탐(2026-09-30).
CMD_POS = r'(?:^|[;&|(]|\b(?:sudo|env|xargs|nohup|timeout\s+\S+))\s*(?:\S*/)?'
SHELL_CLICK = re.compile(CMD_POS + r'(?:cliclick\b|adb\b[^\n;&|]*\bshell\s+input\b'
                         r'|osascript\b[^\n;&|]*\bclick\b)', re.M)
SHELL_CLICK_MSG = ('셸 좌표 클릭(cliclick·adb shell input·osascript click)은 쓰지 않습니다. '
                   '웹은 chrome-devtools, 앱은 mobile-mcp, macOS 네이티브는 peekaboo로 화면 요소를 보고 조작하세요.')


def deny(reason):
    print(json.dumps({'hookSpecificOutput': {
        'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
        'permissionDecisionReason': reason}}, ensure_ascii=False))
    return True


def deny_unbounded_wait(tool_input, command):
    if not (isinstance(tool_input, dict) and tool_input.get('run_in_background')):
        return False
    if not WAIT_LOOP.search(command) or BOUNDED.search(command):
        return False
    print(json.dumps({'hookSpecificOutput': {
        'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
        'permissionDecisionReason': UNBOUNDED_MSG}}, ensure_ascii=False))
    return True


def main():
    notes = []
    try:
        event = json.load(sys.stdin)
        tool_input = event.get('tool_input') if isinstance(event, dict) else None
        command = tool_input.get('command') if isinstance(tool_input, dict) else None
        if not isinstance(command, str):
            command = ''
    except (ValueError, TypeError, OSError):
        tool_input, command = None, ''
    if command and deny_unbounded_wait(tool_input, command):
        return
    if command and SHELL_CLICK.search(command):
        deny(SHELL_CLICK_MSG)
        return
    if command and LONG_RUNNING.search(command) and not os.environ.get('TMUX'):
        notes.append('장시간 실행 가능한 명령입니다. 필요하면 tmux를 쓰세요: '
                     'tmux new -s dev && tmux attach -t dev')
    if command and PUSH.search(command):
        notes.append('원격 반영 명령입니다. 디버그 코드(console.log, print)와 '
                     '자격증명이 남아 있지 않은지 먼저 확인하세요.')
    if notes:
        print(json.dumps({'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'additionalContext': '\n'.join(notes)}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
