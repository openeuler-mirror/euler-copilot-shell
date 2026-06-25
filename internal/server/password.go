package server

import (
	"crypto/rand"
	"encoding/base64"
	"encoding/hex"
	"fmt"
)

const passwordBytes = 32

// GeneratePassword creates a cryptographically random password suitable for
// HTTP Basic Auth with the opencode server. It returns a 64-character
// hex-encoded string derived from 32 random bytes.
//
// Security: uses crypto/rand (not math/rand). The password is never logged.
func GeneratePassword() (string, error) {
	buf := make([]byte, passwordBytes)
	if _, err := rand.Read(buf); err != nil {
		return "", fmt.Errorf("generate random password: %w", err)
	}
	return hex.EncodeToString(buf), nil
}

// basicAuthHeader returns the value for an HTTP Authorization header using
// the Basic scheme. The username is always "opencode".
func basicAuthHeader(password string) string {
	auth := "opencode:" + password
	return "Basic " + base64.StdEncoding.EncodeToString([]byte(auth))
}
