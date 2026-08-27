import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.reporevive.app',
  appName: 'RepoRevive',
  webDir: 'dist',
  plugins: {
    // Route fetch/XHR through Capacitor's native HTTP layer on Android so the
    // bundled webview can call the combined Render origin without CORS setup.
    CapacitorHttp: {
      enabled: true,
    },
  },
};

export default config;
