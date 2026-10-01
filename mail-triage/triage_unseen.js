// 모든 메일함(보낸메일·임시보관·스팸·휴지통 제외)의 안 읽은 메일을 본문까지 출력하고 읽음 처리한다.
// 출력은 사람이 읽는 요약 겸 LLM 에이전트 입력으로 쓴다. 메일 속 링크는 [링크]로 바꿔 에이전트가 따라가지 못하게 한다.
// 실행: node triage_unseen.js [--peek]   (--peek: 읽음 처리하지 않고 출력만)
// 환경변수: IMAP_HOST(기본 imap.naver.com), IMAP_USER, IMAP_PASS — .env 또는 셸에서 넣는다.
require('dotenv').config({ quiet: true });
const { ImapFlow } = require('imapflow');
const { simpleParser } = require('mailparser');

const PEEK = process.argv.includes('--peek');
const BODY_LIMIT = 1500;

// 본문에서 추적 링크를 지우고 공백을 정리
function cleanText(text) {
  return (text || '')
    .replace(/https?:\/\/\S+/g, '[링크]')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, BODY_LIMIT);
}

// 보낸메일·임시보관·스팸·휴지통은 확인 대상에서 제외
const SKIP_SPECIAL_USE = new Set(['\\Sent', '\\Drafts', '\\Junk', '\\Trash']);

// 메일함 하나의 안 읽은 메일을 출력하고 읽음 처리, 처리한 개수를 돌려줌
async function processMailbox(client, path) {
  const lock = await client.getMailboxLock(path);
  try {
    const uids = await client.search({ seen: false }, { uid: true });
    console.log(`\n##### [${path}] 안 읽은 메일 ${uids.length}통`);
    for (const uid of uids) {
      const msg = await client.fetchOne(uid, { source: true }, { uid: true });
      const p = await simpleParser(msg.source);
      const date = p.date ? p.date.toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' }) : '';
      console.log(`\n=== [${path}] UID ${uid} | ${date} | ${p.from ? p.from.text : ''}`);
      console.log(`제목: ${p.subject || ''}`);
      console.log(cleanText(p.text));
    }
    if (uids.length && !PEEK) {
      await client.messageFlagsAdd(uids, ['\\Seen'], { uid: true });
      console.log(`\n[${path}] 읽음 처리 ${uids.length}통`);
    }
    return uids.length;
  } finally {
    lock.release();
  }
}

async function main() {
  const client = new ImapFlow({
    host: process.env.IMAP_HOST || 'imap.naver.com', port: 993, secure: true, logger: false,
    socketTimeout: 60000,
    auth: { user: process.env.IMAP_USER, pass: process.env.IMAP_PASS },
  });
  await client.connect();
  try {
    // 안 읽은 메일이 있는 메일함만 고른다(받은편지함만 보면 프로모션·청구 폴더를 놓친다)
    const boxes = await client.list({ statusQuery: { unseen: true } });
    const targets = boxes.filter((b) => !SKIP_SPECIAL_USE.has(b.specialUse)
      && b.status && b.status.unseen > 0);
    let total = 0;
    for (const b of targets) total += await processMailbox(client, b.path);
    console.log(`안 읽은 메일 ${total}통 (확인한 메일함 ${targets.length}개, 스팸·휴지통 제외)`);
  } finally {
    await client.logout();
  }
}

main().catch((e) => {
  console.error(`IMAP 오류: ${e.message}`);
  process.exit(1);
});
