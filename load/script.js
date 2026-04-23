import http from 'k6/http';
import { check, group, sleep } from 'k6';

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
  const headers = { 'Content-Type': 'application/json' };
  const itemName = `vu-${__VU}-iter-${__ITER}`;

  group('synthetic work', () => {
    const response = http.get(`${targetUrl}/work?work_ms=${workMs}&fail_pct=${failPct}`);

    check(response, {
      'work endpoint returned 2xx': (res) => res.status >= 200 && res.status < 300,
    });
  });

  group('crud flow', () => {
    const createResponse = http.post(
      `${targetUrl}/items`,
      JSON.stringify({
        name: itemName,
        description: 'created by k6 adaptive flow',
        price: 10 + (__ITER % 100),
      }),
      { headers },
    );

    const createOk = check(createResponse, {
      'POST /items returned 201': (res) => res.status === 201,
    });

    if (!createOk) {
      return;
    }

    const itemId = createResponse.json('id');
    const readResponse = http.get(`${targetUrl}/items/${itemId}`);
    check(readResponse, {
      'GET /items/{id} returned 200': (res) => res.status === 200,
    });

    const updateResponse = http.put(
      `${targetUrl}/items/${itemId}`,
      JSON.stringify({
        name: `${itemName}-updated`,
        description: 'updated by k6 adaptive flow',
        price: 20 + (__ITER % 100),
      }),
      { headers },
    );
    check(updateResponse, {
      'PUT /items/{id} returned 200': (res) => res.status === 200,
    });

    const deleteResponse = http.del(`${targetUrl}/items/${itemId}`);
    check(deleteResponse, {
      'DELETE /items/{id} returned 204': (res) => res.status === 204,
    });
  });

  sleep(sleepSeconds);
}
