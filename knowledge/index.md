# FSQ Agent Knowledge Index

This file is loaded for every task as concise project and app knowledge.

## Edge Android MSA Sign-In

Use the account plus password sign-in path for Microsoft account setup.

- The sign-in entry can be reached from the New Tab Page account area or from the Edge overflow menu.
- If the account panel shows a signed-out state such as `Sign in to sync`, tap that sign-in entry before continuing account-dependent cases.
- After entering the account email and moving forward, do not assume the next screen is the password field.
- If the Microsoft sign-in flow shows verification, passkey, authenticator, or another non-password option, look for an option like `Other ways to sign in`, `Use another way`, `Choose another sign-in option`, or similar wording.
- In the alternate sign-in options, choose the password-based sign-in method, then enter `TEST_ACCOUNT_PASSWORD` using the `get_runtime_secret` tool.
- Use `TEST_ACCOUNT_EMAIL` and `TEST_ACCOUNT_PASSWORD` only through `get_runtime_secret`; never print or report their values.
- After submitting the password, verify the signed-in Edge account marker before continuing to account-dependent actions such as opening Microsoft Rewards.
