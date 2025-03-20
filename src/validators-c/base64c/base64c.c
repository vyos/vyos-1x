/*
 * Copyright (C) 2025 VyOS maintainers and contributors
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2 or later as
 * published by the Free Software Foundation.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <ctype.h>

// Function to check if a character is a valid Base64 character
bool is_valid_base64_char(char c) {
    return (isalnum(c) || c == '+' || c == '/' || c == '=');
}

// Function to check if a given string is a valid Base64 encoded string
bool is_valid_base64(const char *str) {
    size_t len = strlen(str);

    // Base64 encoded strings should have a length that is a multiple of 4
    if (len % 4 != 0) {
        return false;
    }

    // Check each character in the string to ensure it's a valid Base64 character
    for (size_t i = 0; i < len; i++) {
        if (!is_valid_base64_char(str[i])) {
            return false;
        }
    }

    return true;
}

int main(int argc, char *argv[]) {
    // Ensure the correct number of arguments are provided
    if (argc < 2 || argc > 4) {
        printf("Usage: %s <base64_string> [--data-length 32|64|128]\n", argv[0]);
        return 1;
    }

    const char *b64_str = argv[1]; // First argument is the Base64 string

    // Validate the Base64 string
    if (!is_valid_base64(b64_str)) {
        printf("Invalid Base64\n");
        return 1;
    }

    // Approximate decoded length calculation:
    // Each 4 Base64 characters represent 3 decoded bytes
    size_t decoded_len = (strlen(b64_str) * 3) / 4;

    // Correct the length if padding exists
    if (b64_str[strlen(b64_str) - 1] == '=') decoded_len--;
    if (b64_str[strlen(b64_str) - 2] == '=') decoded_len--;

    int required_length = -1;  // Default: No required length is specified

    // If a second argument (optional) is provided, check if it's --data-length
    if (argc == 4) {
        if (strcmp(argv[2], "--data-length") == 0) { 
            // Convert the provided data length value from string to integer
            required_length = atoi(argv[3]);

            // Ensure the provided length is one of the allowed values
            if (required_length != 32 && required_length != 64 && required_length != 128) {
                printf("Invalid data length. Allowed: 32, 64, 128\n");
                return 1;
            }
        } else {
            // If an unknown argument is provided, print an error message
            printf("Invalid argument: %s\n", argv[2]);
            return 1;
        }
    }

    // If a required length was specified, check if the decoded length matches
    if (required_length != -1 && decoded_len != required_length) {
        printf("Decoded data length mismatch: expected %d, got %zu\n", required_length, decoded_len);
        return 1;
    }

    printf("Valid Base64\n");
    return 0;
}
