<?php
/**
 * "Login with WHMCS" launcher — deploy to the WHMCS web root.
 *
 * A DeployUnit customer clicks "Continue with WHMCS" on the DeployUnit login
 * page; DeployUnit sends them here. This page authenticates them with their
 * normal WHMCS login (redirecting to the WHMCS login form if needed), then
 * asks the DeployUnit internal API for a one-time SSO link for that customer's
 * e-mail and forwards the browser to it — landing them logged into DeployUnit.
 *
 * No WHMCS password ever reaches DeployUnit; WHMCS is the identity source,
 * exactly like the GitHub OAuth button.
 *
 * Config is read entirely from the existing DeployUnit server record
 * (Setup > Products/Services > Servers): hostname = DeployUnit host,
 * Access Hash = the backend INTERNAL_API_KEY. No extra constants needed.
 */

use WHMCS\Database\Capsule;

require __DIR__ . '/init.php';

$ca = new WHMCS\ClientArea();

// 1. Require a logged-in client. WHMCS bounces to its own login and returns
//    here afterwards via ?goto=.
if (!$ca->isLoggedIn()) {
    $self = 'deployunit-sso.php';
    header('Location: ' . rtrim($GLOBALS['CONFIG']['SystemURL'], '/') . '/login.php?goto=' . urlencode($self));
    exit;
}

$clientId = (int) $_SESSION['uid'];
$client = Capsule::table('tblclients')->where('id', $clientId)->first();
if (!$client) {
    deployunit_sso_fail('We could not identify your account. Please sign in again.');
}

// 2. Read the DeployUnit connection from its server record.
$server = Capsule::table('tblservers')
    ->where('type', 'deployunit')
    ->where('disabled', 0)
    ->orderBy('id')
    ->first();
if (!$server) {
    deployunit_sso_fail('DeployUnit is not configured on this system.');
}

$host = $server->hostname !== '' ? $server->hostname : $server->ipaddress;
$secure = (string) $server->secure !== '' && $server->secure !== '0';
$scheme = $secure ? 'https' : 'http';
$key = $server->accesshash !== '' ? $server->accesshash : $server->password;
if ($host === '' || $key === '') {
    deployunit_sso_fail('DeployUnit connection is incomplete.');
}

// 3. Ask DeployUnit for a one-time SSO link for this customer's e-mail.
$ch = curl_init($scheme . '://' . rtrim($host, '/') . '/api/internal/sso');
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POST => true,
    CURLOPT_TIMEOUT => 20,
    CURLOPT_HTTPHEADER => [
        'X-Internal-Key: ' . $key,
        'Content-Type: application/json',
        'Accept: application/json',
    ],
    CURLOPT_POSTFIELDS => json_encode(['email' => $client->email, 'return_to' => '/app']),
]);
$raw = curl_exec($ch);
$httpCode = (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
curl_close($ch);

$data = json_decode((string) $raw, true);

// 4. Forward to the login link, or explain why not.
if ($httpCode === 404) {
    deployunit_sso_fail(
        'Your account does not have a DeployUnit service yet. Order one from the client area to get access.',
        'No DeployUnit service'
    );
}
if ($httpCode >= 400 || empty($data['url'])) {
    $msg = is_array($data) && !empty($data['detail']) ? (string) $data['detail'] : 'Could not start your DeployUnit session.';
    deployunit_sso_fail($msg);
}

header('Location: ' . $data['url']);
exit;

/**
 * Minimal styled error page — we are outside the WHMCS template context here.
 */
function deployunit_sso_fail(string $message, string $title = 'DeployUnit sign-in')
{
    $systemUrl = rtrim($GLOBALS['CONFIG']['SystemURL'] ?? '', '/');
    http_response_code(400);
    header('Content-Type: text/html; charset=utf-8');
    echo '<!doctype html><html><head><meta charset="utf-8"><title>' . htmlspecialchars($title) . '</title>'
        . '<meta name="viewport" content="width=device-width, initial-scale=1">'
        . '<style>body{background:#070b16;color:#dbe4f3;font-family:system-ui,sans-serif;display:flex;'
        . 'min-height:100vh;align-items:center;justify-content:center;margin:0}'
        . '.box{max-width:420px;padding:32px;border:1px solid rgba(56,189,248,.2);border-radius:16px;'
        . 'background:#0d1526}h1{font-size:18px;margin:0 0 12px}p{color:#8fa3bf;font-size:14px;line-height:1.6}'
        . 'a{display:inline-block;margin-top:18px;color:#38bdf8;text-decoration:none;font-size:13px}</style></head>'
        . '<body><div class="box"><h1>' . htmlspecialchars($title) . '</h1><p>' . htmlspecialchars($message) . '</p>'
        . '<a href="' . htmlspecialchars($systemUrl) . '/clientarea.php">← Back to the client area</a></div></body></html>';
    exit;
}
