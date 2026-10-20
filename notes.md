# Packages for Keyring
The goal is to have a unified set of packages for implementing a nonportable keyring for a wide range of operating environments
These packages are one of the same.
rust-native-keyring is the python wrapper for keyring-rs

- keyring-rs
- rust-native-keyring

# Python Example

```python

import secrets
import rust_native_keyring as rnk

# rust_native_keyring has no module-level get_password/set_password functions.
# Secrets are accessed through an Entry(service, user) object instead.
#
# Entry.get_password()/set_password() are for text secrets (str).
# Entry.get_secret()/set_secret() are for binary secrets (bytes) - use these for raw key material.
#
# A credential store must be selected before creating an Entry. Entry.new() uses
# the platform default (macOS Keychain, Windows Credential Manager, Linux Secret
# Service) and raises RuntimeError("NoDefaultStore") if none is available, e.g. on
# headless Linux. rnk.use_named_store(...) picks an explicit store instead; "sample"
# is a portable, file-backed store that works everywhere.
class RustNativeCryptoVault:
    """An elegant Python wrapper powered by compiled Rust keyring bindings."""

    def __init__(self, service_name: str = "my_rust_vault", backing_file: str = "vault.ron"):
        self.service = service_name
        rnk.use_named_store("sample", {"backing-file": backing_file})

    def save_bytes(self, key_name: str, data: bytes) -> None:
        """Saves a 32-byte array into the credential store."""
        if len(data) != 32:
            raise ValueError("Payload constraint error: Data must be exactly 32 bytes.")

        rnk.Entry(self.service, key_name).set_secret(data)

    def get_bytes(self, key_name: str) -> bytes:
        """Retrieves the 32-byte array from the credential store."""
        try:
            return rnk.Entry(self.service, key_name).get_secret()
        except RuntimeError as exc:
            raise KeyError(f"The key identification identifier '{key_name}' was not found.") from exc

    def delete_bytes(self, key_name: str) -> None:
        """Purges the secret completely from the host secure store."""
        rnk.Entry(self.service, key_name).delete_credential()


# ==========================================
# Execution Loop Example
# ==========================================
if __name__ == "__main__":
    # Initialize our Rust-backed secure vault
    vault = RustNativeCryptoVault()

    # 1. Create a true random 32-byte block array
    original_block = secrets.token_bytes(32)
    print(f"[+] Original 32-Byte Payload: {original_block.hex()}")

    # 2. Store it via compiled Rust binary routine
    print("[+] Sending data payload across PyO3 layer into Rust-Native-Keyring...")
    vault.save_bytes("app_encryption_seed", original_block)

    # 3. Fetch it back cleanly elsewhere
    retrieved_block = vault.get_bytes("app_encryption_seed")
    print(f"[+] Successfully extracted back to Python: {retrieved_block.hex()}")

    # Verify identical bytes
    assert original_block == retrieved_block, "Cryptographic integrity failure!"
    print("[+] Success: The payload is locked in the host hardware vault.")


```

# Rust Example
```rust

// keyring's default ("v1") feature exposes Entry at the crate root with
// get_secret()/set_secret() for raw bytes, so no manual string encoding is
// needed. Entry::new() uses the platform-default credential store and returns
// Err(Error::NoDefaultStore) if none is available (e.g. headless Linux).
// The correct teardown method is delete_credential(), not delete_password().
use keyring::{Entry, Result};
use rand::RngCore;

pub struct RustNativeCryptoVault {
    service: String,
}

impl RustNativeCryptoVault {
    /// Creates a new vault instance assigned to a specific application namespace.
    pub fn new(service_name: &str) -> Self {
        Self {
            service: service_name.to_string(),
        }
    }

    /// Stores a 32-byte array into the non-portable OS credential store.
    pub fn save_bytes(&self, key_name: &str, data: &[u8; 32]) -> Result<()> {
        let entry = Entry::new(&self.service, key_name)?;
        entry.set_secret(data)?;
        Ok(())
    }

    /// Retrieves the 32-byte array from the host credential store.
    pub fn get_bytes(&self, key_name: &str) -> Result<[u8; 32]> {
        let entry = Entry::new(&self.service, key_name)?;
        let secret = entry.get_secret()?;

        let mut data_bytes = [0u8; 32];
        data_bytes.copy_from_slice(&secret[..32]);
        Ok(data_bytes)
    }

    /// Purges the secret entry from the host credential store.
    pub fn delete_bytes(&self, key_name: &str) -> Result<()> {
        let entry = Entry::new(&self.service, key_name)?;
        entry.delete_credential()?;
        Ok(())
    }
}

fn main() -> Result<()> {
    // Initialize our Rust native security vault
    let vault = RustNativeCryptoVault::new("my_rust_vault");
    let key_identifier = "app_encryption_seed";

    // 1. Securely generate a random 32-byte cryptographic array
    let mut original_block = [0u8; 32];
    rand::rng().fill_bytes(&mut original_block);

    println!("[+] Original 32-Byte Payload: ");
    for byte in &original_block { print!("{:02x}", byte); }
    println!("\n");

    // 2. Commit the data payload directly to the host's secure hardware store
    println!("[+] Committing payload to native host credential subsystem...");
    vault.save_bytes(key_identifier, &original_block)?;

    // 3. Extract the block back into our runtime environment
    let retrieved_block = vault.get_bytes(key_identifier)?;

    println!("[+] Successfully extracted back from OS vault: ");
    for byte in &retrieved_block { print!("{:02x}", byte); }
    println!("\n");

    // 4. Verify identical structural byte-match execution
    assert_eq!(original_block, retrieved_block, "Cryptographic integrity failure!");
    println!("[+] Success: The payload is locked in the host hardware vault.");

    // Optional: Clean up after ourselves if needed
    // vault.delete_bytes(key_identifier)?;

    Ok(())
}


```

`keyring = "4"` is sufficient in `Cargo.toml`; the `v1` feature used above is enabled by default.