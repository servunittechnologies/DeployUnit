<?php
/**
 * WHMCS provisioning module for DeployUnit.
 *
 * WHMCS owns orders/invoices/dunning; DeployUnit owns the product experience.
 * This module is intentionally thin: it provisions the DeployUnit account via
 * the internal API and hands the customer off to the dashboard with SSO.
 *
 * Server record: hostname = DeployUnit host (deployunit.com, Secure on),
 * Access Hash = the backend's INTERNAL_API_KEY value.
 */

if (!defined('WHMCS')) {
    die('This file cannot be accessed directly');
}

require_once __DIR__ . '/lib/Api.php';

use WHMCS\Module\Server\DeployUnit\Api;

function deployunit_MetaData()
{
    return [
        'DisplayName' => 'DeployUnit',
        'APIVersion' => '1.1',
        'RequiresServer' => true,
        'DefaultSSLPort' => '443',
        'ServiceSingleSignOnLabel' => 'Open DeployUnit',
    ];
}

function deployunit_ConfigOptions()
{
    return [
        'Plan' => [
            'Type' => 'dropdown',
            'Loader' => 'deployunit_PlanLoader',
            'SimpleMode' => true,
            'Description' => 'The DeployUnit plan this product provisions.',
        ],
    ];
}

function deployunit_PlanLoader(array $params)
{
    $response = Api::fromParams($params)->get('/plans');
    $options = [];
    foreach ((array) ($response['plans'] ?? []) as $plan) {
        if (empty($plan['id'])) {
            continue;
        }
        $label = (string) ($plan['name'] ?? $plan['id']);
        if (isset($plan['price_eur'])) {
            $label .= ' (€' . number_format((float) $plan['price_eur'], 2) . '/mo)';
        }
        $options[(string) $plan['id']] = $label;
    }
    if (!$options) {
        throw new Exception('No plans returned by the DeployUnit API. Check the internal key.');
    }
    return $options;
}

function deployunit_TestConnection(array $params)
{
    try {
        Api::fromParams($params)->get('/plans');
        return ['success' => true, 'error' => ''];
    } catch (\Throwable $e) {
        logModuleCall('deployunit', __FUNCTION__, deployunit_redact($params), $e->getMessage());
        return ['success' => false, 'error' => $e->getMessage()];
    }
}

// ---------------------------------------------------------------- lifecycle

function deployunit_CreateAccount(array $params)
{
    try {
        $client = $params['clientsdetails'] ?? [];
        $name = trim((string) (($client['firstname'] ?? '') . ' ' . ($client['lastname'] ?? '')));
        $response = Api::fromParams($params)->post('/provision', [
            'email' => (string) ($client['email'] ?? ''),
            'name' => $name !== '' ? $name : 'Customer',
            'plan' => (string) ($params['configoption1'] ?? 'free'),
            'external_ref' => (string) $params['serviceid'],
        ]);
        if (isset($params['model']) && is_object($params['model'])) {
            $params['model']->serviceProperties->save([
                'deployunit_user_id' => (string) ($response['user_id'] ?? ''),
                'deployunit_workspace_id' => (string) ($response['workspace_id'] ?? ''),
            ]);
        }
        return 'success';
    } catch (\Throwable $e) {
        logModuleCall('deployunit', __FUNCTION__, deployunit_redact($params), $e->getMessage(), $e->getTraceAsString());
        return $e->getMessage();
    }
}

function deployunit_SuspendAccount(array $params)
{
    try {
        Api::fromParams($params)->post('/suspend', ['external_ref' => (string) $params['serviceid']]);
        return 'success';
    } catch (\Throwable $e) {
        logModuleCall('deployunit', __FUNCTION__, deployunit_redact($params), $e->getMessage());
        return $e->getMessage();
    }
}

function deployunit_UnsuspendAccount(array $params)
{
    try {
        Api::fromParams($params)->post('/unsuspend', ['external_ref' => (string) $params['serviceid']]);
        return 'success';
    } catch (\Throwable $e) {
        logModuleCall('deployunit', __FUNCTION__, deployunit_redact($params), $e->getMessage());
        return $e->getMessage();
    }
}

function deployunit_TerminateAccount(array $params)
{
    try {
        Api::fromParams($params)->post('/terminate', [
            'external_ref' => (string) $params['serviceid'],
            'delete_user' => false,
        ]);
        return 'success';
    } catch (\Throwable $e) {
        logModuleCall('deployunit', __FUNCTION__, deployunit_redact($params), $e->getMessage());
        return $e->getMessage();
    }
}

function deployunit_ChangePackage(array $params)
{
    try {
        Api::fromParams($params)->post('/plan', [
            'external_ref' => (string) $params['serviceid'],
            'plan' => (string) ($params['configoption1'] ?? 'free'),
        ]);
        return 'success';
    } catch (\Throwable $e) {
        logModuleCall('deployunit', __FUNCTION__, deployunit_redact($params), $e->getMessage());
        return $e->getMessage();
    }
}

function deployunit_Renew(array $params)
{
    return 'success';
}

// ---------------------------------------------------------------- SSO

function deployunit_ServiceSingleSignOn(array $params)
{
    try {
        $response = Api::fromParams($params)->post('/sso', ['external_ref' => (string) $params['serviceid']]);
        if (empty($response['url'])) {
            throw new \RuntimeException('No SSO url returned.');
        }
        return ['success' => true, 'redirectTo' => (string) $response['url']];
    } catch (\Throwable $e) {
        logModuleCall('deployunit', __FUNCTION__, deployunit_redact($params), $e->getMessage());
        return ['success' => false, 'errorMsg' => $e->getMessage()];
    }
}

function deployunit_ClientAreaAllowedFunctions()
{
    return ['openPanel'];
}

function deployunit_openPanel(array $params)
{
    try {
        $response = Api::fromParams($params)->post('/sso', ['external_ref' => (string) $params['serviceid']]);
        if (!empty($response['url']) && !headers_sent()) {
            header('Location: ' . $response['url']);
            exit;
        }
        return 'success';
    } catch (\Throwable $e) {
        logModuleCall('deployunit', __FUNCTION__, deployunit_redact($params), $e->getMessage());
        return $e->getMessage();
    }
}

// ---------------------------------------------------------------- client area

function deployunit_ClientArea(array $params)
{
    $vars = [
        'serviceStatus' => (string) ($params['status'] ?? ''),
        'planName' => '',
        'isActive' => true,
        'usage' => [],
        'limits' => [],
        'credits' => 0,
        'workspaces' => [],
        'apiError' => '',
    ];
    try {
        $status = Api::fromParams($params)->get('/status', ['external_ref' => (string) $params['serviceid']]);
        $vars['planName'] = (string) ($status['plan']['name'] ?? '');
        $vars['isActive'] = (bool) ($status['is_active'] ?? true);
        $vars['usage'] = (array) ($status['usage'] ?? []);
        $vars['limits'] = (array) ($status['plan']['limits'] ?? []);
        $vars['credits'] = (int) ($status['credits_balance'] ?? 0);
        $vars['workspaces'] = (array) ($status['workspaces'] ?? []);
    } catch (\Throwable $e) {
        $vars['apiError'] = $e->getMessage();
        logModuleCall('deployunit', __FUNCTION__, deployunit_redact($params), $e->getMessage());
    }

    return [
        'tabOverviewReplacementTemplate' => 'templates/panel.tpl',
        'templateVariables' => $vars,
    ];
}

// ---------------------------------------------------------------- admin

function deployunit_AdminServicesTabFields(array $params)
{
    try {
        $status = Api::fromParams($params)->get('/status', ['external_ref' => (string) $params['serviceid']]);
        $usage = (array) ($status['usage'] ?? []);
        $summary = [];
        foreach (['apps', 'domains', 'databases', 'workspaces'] as $key) {
            if (isset($usage[$key])) {
                $summary[] = $key . ': ' . $usage[$key];
            }
        }
        return [
            'DeployUnit User' => htmlspecialchars((string) ($status['email'] ?? '-'), ENT_QUOTES)
                . ' (' . htmlspecialchars((string) ($status['user_id'] ?? ''), ENT_QUOTES) . ')',
            'Plan' => htmlspecialchars((string) ($status['plan']['name'] ?? '-'), ENT_QUOTES),
            'Active' => !empty($status['is_active']) ? 'yes' : 'no (suspended)',
            'Usage' => htmlspecialchars(implode(' · ', $summary) ?: '-', ENT_QUOTES),
            'Credits' => (int) ($status['credits_balance'] ?? 0),
        ];
    } catch (\Throwable $e) {
        return ['DeployUnit' => htmlspecialchars($e->getMessage(), ENT_QUOTES)];
    }
}

// ---------------------------------------------------------------- helpers

function deployunit_redact(array $params)
{
    foreach (['serveraccesshash', 'serverpassword', 'password'] as $key) {
        if (!empty($params[$key])) {
            $params[$key] = '***redacted***';
        }
    }
    unset($params['model']);
    return $params;
}
