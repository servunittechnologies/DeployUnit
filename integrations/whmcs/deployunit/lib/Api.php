<?php

namespace WHMCS\Module\Server\DeployUnit;

/**
 * Client for the DeployUnit internal provisioning API
 * (backend/routers/internal_provisioning.py). The WHMCS server record maps:
 * hostname = DeployUnit host (e.g. deployunit.com), Access Hash = the value
 * of the backend INTERNAL_API_KEY env var.
 */
class Api
{
    /** @var string */
    private $baseUrl;

    /** @var string */
    private $key;

    public function __construct(string $host, string $key, bool $secure = true)
    {
        $host = trim($host);
        if (preg_match('#^(https?)://#i', $host, $m)) {
            $secure = strtolower($m[1]) === 'https';
            $host = preg_replace('#^https?://#i', '', $host);
        }
        $host = rtrim($host, '/');
        if ($host === '') {
            throw new \RuntimeException('No DeployUnit hostname configured on the WHMCS server record.');
        }
        if (trim($key) === '') {
            throw new \RuntimeException('No internal API key configured. Put the INTERNAL_API_KEY value in the server\'s Access Hash field.');
        }
        $this->baseUrl = ($secure ? 'https' : 'http') . '://' . $host . '/api/internal';
        $this->key = trim($key);
    }

    public static function fromParams(array $params): self
    {
        $host = !empty($params['serverhostname']) ? $params['serverhostname'] : ($params['serverip'] ?? '');
        $key = trim((string) ($params['serveraccesshash'] ?? ''));
        if ($key === '') {
            $key = trim((string) ($params['serverpassword'] ?? ''));
        }
        $secure = !isset($params['serversecure']) || !in_array($params['serversecure'], ['', '0', false, null], true);
        return new self((string) $host, $key, $secure);
    }

    public function get(string $path, array $query = []): array
    {
        return $this->request('GET', $path, $query);
    }

    public function post(string $path, array $body = []): array
    {
        return $this->request('POST', $path, [], $body);
    }

    private function request(string $method, string $path, array $query = [], ?array $body = null): array
    {
        $url = $this->baseUrl . $path;
        if ($query) {
            $url .= '?' . http_build_query($query);
        }
        $ch = curl_init($url);
        $headers = [
            'X-Internal-Key: ' . $this->key,
            'Accept: application/json',
        ];
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_CUSTOMREQUEST => $method,
            CURLOPT_TIMEOUT => 60,
            CURLOPT_CONNECTTIMEOUT => 10,
        ]);
        if ($body !== null && $method !== 'GET') {
            $headers[] = 'Content-Type: application/json';
            curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($body));
        }
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);

        $raw = curl_exec($ch);
        $errno = curl_errno($ch);
        $error = curl_error($ch);
        $httpCode = (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE);

        $decoded = json_decode((string) $raw, true);
        if (function_exists('logModuleCall')) {
            logModuleCall('deployunit', $method . ' ' . $path, ['query' => $query, 'body' => $body], (string) $raw, $decoded, [$this->key]);
        }

        if ($errno !== 0) {
            throw new \RuntimeException('Could not reach the DeployUnit API (' . $error . ').');
        }
        if ($httpCode >= 400) {
            $message = 'HTTP ' . $httpCode;
            if (is_array($decoded) && !empty($decoded['detail'])) {
                $message = is_string($decoded['detail']) ? $decoded['detail'] : json_encode($decoded['detail']);
            }
            throw new \RuntimeException('DeployUnit: ' . $message);
        }

        return is_array($decoded) ? $decoded : [];
    }
}
