// Email sign-up for the weekly digest, through MailerLite.
//
// Fill in ONE of these. While both are empty the sign-up box stays hidden.
//   formAction  the address an embedded MailerLite form posts to. It is the action="…" value
//               in the form's embed code and looks like
//               https://assets.mailerlite.com/jsonp/123456/forms/1234567890/subscribe
//   pageUrl     the address of a MailerLite sign-up page, if embedded forms aren't available
//               on the account's plan. The box then shows a button that opens that page.
const SIGNUP = { formAction: "", pageUrl: "" };

(function () {
  const box = document.getElementById("signup");
  if (!box || !(SIGNUP.formAction || SIGNUP.pageUrl)) return;
  const root = document.currentScript.src.replace(/signup\.js.*$/, ""); // works from any folder

  box.innerHTML = `
    <h2>Get the weekly digest by email</h2>
    <p>One email each Saturday: who missed votes, whose grade changed and which bills became law. Unsubscribe any time.</p>
    ${SIGNUP.formAction
      ? `<form id="signup-form">
           <input type="email" id="signup-email" required placeholder="you@example.com" aria-label="Email address" autocomplete="email">
           <button>Sign up</button>
         </form>
         <p class="signup-note" id="signup-note" role="status"></p>`
      : `<p><a class="button" href="${SIGNUP.pageUrl}" target="_blank" rel="noopener">Sign up ↗</a></p>`}
    <p class="fineprint"><a href="${root}digest/">Read the latest digest</a> · <a href="${root}privacy.html">Privacy policy</a></p>`;
  box.hidden = false;

  const form = document.getElementById("signup-form");
  if (!form) return;
  const note = document.getElementById("signup-note");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const button = form.querySelector("button");
    const body = new FormData();
    body.append("fields[email]", document.getElementById("signup-email").value.trim());
    body.append("ml-submit", "1");
    body.append("anticsrf", "true");
    button.disabled = true;
    note.textContent = "Signing you up…";
    try {
      const result = await fetch(SIGNUP.formAction, { method: "POST", body }).then((r) => r.json());
      if (!result.success) throw new Error("rejected");
      form.hidden = true;
      note.textContent = "Thanks for signing up. If a confirmation email arrives, click the link in it to finish.";
    } catch {
      button.disabled = false;
      note.textContent = "That didn't work. Check the address and try again.";
    }
  });
})();
