import http from 'k6/http';
import { check, sleep } from 'k6';

const initialVus = Number(__ENV.INITIAL_VUS || 50);
const maxVus = Number(__ENV.MAX_VUS || 1000);
const targetUrl = __ENV.TARGET_URL || 'http://localhost:8000';
const workMs = __ENV.WORK_MS || '20';
const failPct = __ENV.FAIL_PCT || '0';
const sleepSeconds = Number(__ENV.SLEEP_SECONDS || 1);

export const options = {
  scenarios: {
    adaptive: {
      executor: 'externally-controlled',
      vus: initialVus,
      maxVUs: maxVus,
      duration: __ENV.TEST_DURATION || '1h',
    },
  },
};

export default function () {
  const response = http.get(`${targetUrl}/work?work_ms=${workMs}&fail_pct=${failPct}`);

  check(response, {
    'work endpoint returned 2xx': (res) => res.status >= 200 && res.status < 300,
  });

  sleep(sleepSeconds);
}
