export const fields = form => Object.fromEntries(new FormData(form));

export function inlineError(form, message) {
  const element = form.querySelector('[data-form-error]');
  element.textContent = message;
  element.hidden = !message;
}

export async function submitForm(event, action) {
  event.preventDefault();
  const form = event.target;
  const submitter = event.submitter || form.querySelector('button[type=submit]');
  inlineError(form, '');
  submitter.disabled = true;
  try {
    await action(fields(form), form);
  } catch (error) {
    inlineError(form, error.message);
  } finally {
    submitter.disabled = false;
  }
}

export function notify(message) {
  const notice = document.querySelector('#notice');
  notice.textContent = message;
  clearTimeout(notify.timer);
  notify.timer = setTimeout(() => { notice.textContent = ''; }, 4200);
}
