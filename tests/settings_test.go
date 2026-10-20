package settings

import (
	"bytes"
	"os"
	"path/filepath"
	"testing"
)

func TestNixPrivacyPolicy(t *testing.T) {
	t.Setenv("XDG_CONFIG_HOME", t.TempDir())
	original := []byte(`{"noStats":false,"noUsageStats":false,"noAutoUpdate":false,"noAutoDownload":false,"noAccountDiscovery":false,"theme":"dark"}`)
	if err := os.MkdirAll(filepath.Dir(Path()), 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(Path(), original, 0600); err != nil {
		t.Fatal(err)
	}
	got := Load()
	if !got.NoStats || !got.NoUsageStats || !got.NoAutoUpdate || !got.NoAutoDownload {
		t.Fatal("saved settings re-enabled telemetry or automatic application updates")
	}
	if got.NoAccountDiscovery || got.Theme != "dark" {
		t.Fatal("privacy policy changed account discovery or unrelated preferences")
	}
	disk, err := os.ReadFile(Path())
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(disk, original) {
		t.Fatal("loading policy rewrote the user's settings")
	}
	if err := Save(Settings{NoAccountDiscovery: true}); err != nil {
		t.Fatal(err)
	}
	if !Load().NoAccountDiscovery {
		t.Fatal("account discovery opt-out was lost")
	}
}
