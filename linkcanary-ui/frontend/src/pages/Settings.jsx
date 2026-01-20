import { useState, useEffect } from 'react';
import Card, { CardBody, CardHeader } from '../components/Card';
import Button from '../components/Button';
import Input, { Checkbox } from '../components/Input';
import { settingsApi } from '../services/api';

export default function Settings() {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  
  useEffect(() => {
    loadSettings();
  }, []);
  
  async function loadSettings() {
    try {
      const data = await settingsApi.get();
      setSettings(data);
    } catch (err) {
      console.error('Failed to load settings:', err);
    } finally {
      setLoading(false);
    }
  }
  
  function updateSetting(key, value) {
    setSettings((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  }
  
  async function handleSave() {
    setSaving(true);
    try {
      await settingsApi.update(settings);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      alert('Failed to save settings: ' + err.message);
    } finally {
      setSaving(false);
    }
  }
  
  if (loading) {
    return (
      <div className="text-center py-12">
        <div className="animate-spin inline-block w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full" />
      </div>
    );
  }
  
  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
      
      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold text-gray-900">Crawl Defaults</h2>
          <p className="text-sm text-gray-500">Default settings for new crawls</p>
        </CardHeader>
        <CardBody className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Default delay (seconds)
              </label>
              <input
                type="range"
                min="0.1"
                max="5"
                step="0.1"
                value={settings?.default_delay || 0.5}
                onChange={(e) => updateSetting('default_delay', parseFloat(e.target.value))}
                className="w-full"
              />
              <div className="text-sm text-gray-500 text-center">{settings?.default_delay || 0.5}s</div>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Default timeout (seconds)
              </label>
              <input
                type="range"
                min="5"
                max="60"
                step="5"
                value={settings?.default_timeout || 10}
                onChange={(e) => updateSetting('default_timeout', parseInt(e.target.value))}
                className="w-full"
              />
              <div className="text-sm text-gray-500 text-center">{settings?.default_timeout || 10}s</div>
            </div>
          </div>
          
          <div className="space-y-2">
            <Checkbox
              label="Skip OK links by default"
              checked={settings?.default_skip_ok ?? true}
              onChange={(e) => updateSetting('default_skip_ok', e.target.checked)}
            />
            <Checkbox
              label="Internal links only by default"
              checked={settings?.default_internal_only ?? false}
              onChange={(e) => updateSetting('default_internal_only', e.target.checked)}
            />
          </div>
        </CardBody>
      </Card>
      
      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold text-gray-900">Storage</h2>
          <p className="text-sm text-gray-500">Report storage settings</p>
        </CardHeader>
        <CardBody className="space-y-4">
          <Input
            label="Report retention (days)"
            type="number"
            min="1"
            max="365"
            value={settings?.report_retention_days || 90}
            onChange={(e) => updateSetting('report_retention_days', parseInt(e.target.value))}
          />
          
          <Input
            label="Max storage (MB)"
            type="number"
            min="100"
            max="10000"
            value={settings?.max_storage_mb || 1000}
            onChange={(e) => updateSetting('max_storage_mb', parseInt(e.target.value))}
          />
        </CardBody>
      </Card>
      
      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold text-gray-900">About</h2>
        </CardHeader>
        <CardBody>
          <div className="space-y-2 text-sm text-gray-600">
            <p><strong>LinkCanary UI</strong> v0.1.0</p>
            <p>
              <a
                href="https://github.com/chesterbeard/linkcanary"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                GitHub Repository
              </a>
            </p>
            <p>Licensed under MIT</p>
          </div>
        </CardBody>
      </Card>
      
      <div className="flex items-center gap-4">
        <Button onClick={handleSave} loading={saving}>
          Save Settings
        </Button>
        {saved && (
          <span className="text-green-600 text-sm">Settings saved successfully!</span>
        )}
      </div>
    </div>
  );
}
