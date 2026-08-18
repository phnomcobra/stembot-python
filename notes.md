# Packages for Keyring
The goal is to have a unified set of packages for implementing a nonportable keyring for a wide range of operating environments
These packages are one of the same.
rust-native-keyring is the python wrapper for keyring-rs

- keyring-rs
- rust-native-keyring

# Python Example

```python

import secrets
import rust_native_keyring

class RustNativeCryptoVault:
    """An elegant Python wrapper powered by compiled Rust keyring bindings."""

    def __init__(self, service_name: str = "my_rust_vault"):
        self.service = service_name

    def save_bytes(self, key_name: str, data: bytearray) -> None:
        """Saves a 32-byte array into the non-portable OS credential store via Rust."""
        if len(data) != 32:
            raise ValueError("Payload constraint error: Data must be exactly 32 bytes.")

        # Serialize bytearray to a raw 1:1 string character mapping
        serialized_string = bytes(data).decode('latin1')

        # Direct execution inside the compiled Rust module bindings
        rust_native_keyring.set_password(self.service, key_name, serialized_string)

    def get_bytes(self, key_name: str) -> bytearray:
        """Retrieves and re-assembles the 32-byte array using Rust context."""
        serialized_string = rust_native_keyring.get_password(self.service, key_name)

        if serialized_string is None:
            raise KeyError(f"The key identification identifier '{key_name}' was not found.")

        # Cast the character mapping directly back to a mutable bytearray
        return bytearray(serialized_string.encode('latin1'))

    def delete_bytes(self, key_name: str) -> None:
        """Purges the secret completely from the host secure store."""
        rust_native_keyring.delete_password(self.service, key_name)


# ==========================================
# Execution Loop Example
# ==========================================
if __name__ == "__main__":
    # Initialize our Rust-backed secure vault
    vault = RustNativeCryptoVault()

    # 1. Create a true random 32-byte block array
    original_block = bytearray(secrets.token_bytes(32))
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

        // Safely serialize raw bytes to ISO-8859-1 (latin1) format string
        // This maps byte values 0-255 directly to character codes 0-255 1-to-1
        let serialized_string: String = data.iter().map(|&b| b as char).collect();

        // Pass the string directly into the host OS secure storage engine
        entry.set_password(&serialized_string)?;
        Ok(())
    }

    /// Retrieves and re-assembles the 32-byte array from the host credential store.
    pub fn get_bytes(&self, key_name: &str) -> Result<[u8; 32]> {
        let entry = Entry::new(&self.service, key_name)?;
        let serialized_string = entry.get_password()?;

        // Unpack the character values directly back into raw 8-bit bytes
        let mut data_bytes = [0u8; 32];
        for (i, ch) in serialized_string.chars().enumerate() {
            if i >= 32 { break; }
            data_bytes[i] = ch as u8;
        }

        Ok(data_bytes)
    }

    /// Purges the secret entry from the host credential store.
    pub fn delete_bytes(&self, key_name: &str) -> Result<()> {
        let entry = Entry::new(&self.service, key_name)?;
        entry.delete_password()?;
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