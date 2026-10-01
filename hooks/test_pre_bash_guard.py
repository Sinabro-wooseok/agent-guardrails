"""pre_bash_guard.py 동작 테스트: 훅에 이벤트 JSON을 stdin으로 넣고 거절·통과·안내를 확인한다.

실행: python3 -m unittest hooks/test_pre_bash_guard.py
"""
import json
import os
import subprocess
import sys
import unittest

HOOK = os.path.join(os.path.dirname(__file__), 'pre_bash_guard.py')


def run_hook(command, background=False):
    event = {'tool_name': 'Bash',
             'tool_input': {'command': command, 'run_in_background': background}}
    env = {k: v for k, v in os.environ.items() if k != 'TMUX'}
    out = subprocess.run([sys.executable, HOOK], input=json.dumps(event),
                         capture_output=True, text=True, env=env, timeout=10).stdout
    return json.loads(out)['hookSpecificOutput'] if out.strip() else None


class PreBashGuardTest(unittest.TestCase):
    def test_시한_없는_백그라운드_대기_루프는_거절(self):
        r = run_hook('until curl -s localhost:3000; do sleep 5; done', background=True)
        self.assertEqual(r['permissionDecision'], 'deny')

    def test_timeout이_있는_대기_루프는_통과(self):
        r = run_hook("timeout 900 bash -c 'until curl -s localhost:3000; do sleep 5; done'",
                     background=True)
        self.assertIsNone(r)

    def test_횟수_비교가_있는_루프는_통과(self):
        r = run_hook('i=0; while [ $i -lt 10 ]; do i=$((i+1)); done', background=True)
        self.assertIsNone(r)

    def test_포그라운드_루프는_검사하지_않음(self):
        self.assertIsNone(run_hook('until false; do sleep 1; done'))

    def test_셸_좌표_클릭은_거절(self):
        for cmd in ('cliclick c:100,200', 'adb shell input tap 10 20',
                    'sudo osascript -e "tell app \\"Finder\\" to click"'):
            with self.subTest(cmd=cmd):
                self.assertEqual(run_hook(cmd)['permissionDecision'], 'deny')

    def test_grep_인자_속_단어는_오탐하지_않음(self):
        self.assertIsNone(run_hook('grep -rn "cliclick" docs/'))

    def test_push는_안내만_붙음(self):
        r = run_hook('git push origin main')
        self.assertNotIn('permissionDecision', r)
        self.assertIn('원격 반영', r['additionalContext'])


if __name__ == '__main__':
    unittest.main()
