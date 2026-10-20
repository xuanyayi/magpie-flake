package plugin

import (
	"context"
	"testing"
	"time"
)

func TestNixPluginBackgroundUpdatesCanBeDisabled(t *testing.T) {
	t.Setenv("MAGPIE_NO_PLUGIN_AUTO_UPDATE", "1")
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	done := make(chan struct{})
	go func() {
		KeepUpdated(ctx)
		close(done)
	}()
	select {
	case <-done:
	case <-time.After(time.Second):
		t.Fatal("background updater did not stop when disabled")
	}
}
