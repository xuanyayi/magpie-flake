package stats

import (
	"context"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"sync/atomic"
	"testing"
	"time"

	"github.com/yetone/magpie/internal/settings"
)

func TestNixStatsNeverSend(t *testing.T) {
	t.Setenv("XDG_CONFIG_HOME", t.TempDir())
	t.Setenv("XDG_CACHE_HOME", t.TempDir())
	t.Setenv("DO_NOT_TRACK", "")
	t.Setenv("MAGPIE_NO_STATS", "")
	var requests atomic.Int64
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests.Add(1)
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()
	t.Setenv("MAGPIE_STATS_HOST", server.URL)
	if err := settings.Save(settings.Settings{}); err != nil {
		t.Fatal(err)
	}
	for _, when := range []time.Time{time.Now(), time.Now().Add(24 * time.Hour)} {
		if err := Send(context.Background(), "v0.1.1294", "app", when); err != nil {
			t.Fatal(err)
		}
	}
	if requests.Load() != 0 {
		t.Fatal("statistics reached the collector")
	}
	for _, name := range []string{"install-id", "stats-sent"} {
		if _, err := os.Stat(filepath.Join(settings.Dir(), name)); !os.IsNotExist(err) {
			t.Fatalf("statistics state %s was created or could not be checked: %v", name, err)
		}
	}
}
