# Admin UI Standard - Catalog / Taxonomy / List Pages

## Reference screens

Use these current screens as the visual and layout baseline:

- `Матеріали → Виробники`
- `Матеріали → Постачальники`
- `Фурнітура → Виробники`

New admin screens that are functionally similar should reuse the existing shared shell, CSS, and patterns instead of inventing a new page structure.

## 1. Page shell

The whole screen should behave like one logical white panel.

Inside it:

1. header
2. breadcrumb/title block on the left
3. actions on the right
4. subtitle/description
5. content/table below

Do not create a separate gray header zone outside the white panel when equivalent screens already work inside the white panel.

## 2. Natural height

The white panel should not have a fixed viewport height.

Do not use layout rules that artificially cap content with:

- fixed height
- max-height without a real need
- forced `flex: 1 1 auto` if it prevents the panel from growing
- `minmax(0, 1fr)` as a viewport-like row for a normal long catalog
- nested scroll only through the page wrapper

Standard behavior:

- `height: auto`
- natural content height
- the panel grows with the number of rows/cards
- a long page scrolls like a normal page

Do not let records escape the white frame.

## 3. Breadcrumbs

For nested catalog screens use:

`[Root section] / [Current section]`

Examples:

- `Матеріали / Виробники`
- `Матеріали / Постачальники`
- `Матеріали / Категорії`
- `Фурнітура / Виробники`

The root breadcrumb should be clickable if a back route exists.

Do not repeat the same title below as a second large heading.

## 4. Header actions

On desktop, all controls should sit in one clean row on the right.

Typical order:

- count badge
- search/filter
- ownership/type selector, if needed
- `Показати неактивні`
- `Оновити`
- `+ Додати`

Do not create a separate toolbar row below the header if the controls can live in the header.

The left title/subtitle block and the right actions block should be vertically centered.

Do not use screen-specific `align-items: flex-start`, negative margins, absolute positioning, or other hacks unless there is a functional reason.

On narrow screens, wrapping is allowed.

## 5. Refresh

Do not duplicate global refresh and local refresh.

For a specific catalog, one local `Оновити` button is enough.

## 6. Add button

For similar taxonomy/list screens, use the same text:

`+ Додати`

Do not mix without a strong reason:

- `Створити`
- `Додати`
- `Новий`
- `Create`

## 7. Table row actions

Standard order:

`[Edit] [Активувати / Деактивувати] [Видалити]`

Edit:

- compact icon button

Status:

- text button
- active row -> `Деактивувати`
- inactive row -> `Активувати`

Do not use unclear arrows for active state changes.

Delete:

- text danger action or an approved shared delete pattern
- show only if delete is actually allowed

Actions should stay in one row and should not overlap.

The `Дії` column should be wide enough, but not expand the whole table.

## 8. Delete confirmation

Do not use `window.confirm()`.

Reason:

Browser dialogs show the hostname/address (`127.0.0.1`, domain, etc.) and look like a system popup.

Use a shared internal React modal.

The modal should have:

- title
- human-readable entity name
- `Скасувати`
- `Видалити`
- `X`
- loading state
- backend error display

## 9. Logos / images

Logos should not define row height.

Use a compact logo container with:

`object-fit: contain`

Wide logos should not be cropped or squeezed into a square.

Prefer reusing the existing manufacturer logo pattern instead of creating supplier/manufacturer-specific renderers.

## 10. Table density

Columns should use space rationally.

Do not leave large empty areas for:

- order
- activity
- ownership
- actions
- short status fields

The name column may take more space.

Long values should wrap safely or ellipsis instead of pushing the table off the right edge.

## 11. Ownership display

Do not show raw UUID as the main owner label.

Fallback order:

1. display name
2. username/login
3. email
4. short UUID only as the last fallback

System rows:

`Система` / `Системний`

according to the UI context.

## 12. Shared components first

Before creating new CSS or a new component:

1. find the existing analogue
2. check for a shared component
3. check the existing CSS contract
4. reuse the existing pattern
5. only create a new scoped rule if it is truly necessary

Do not create:

- supplier-specific layout hacks
- manufacturer-specific alignment hacks
- category-specific page shells

if the difference is only in the data.

## 13. Function vs presentation

UI unification must not change business logic.

Do not change without a separate task:

- permissions
- ownership
- API contracts
- DB
- delete dependency rules
- parser
- prices
- canonical model
- upload storage logic

## 14. Reference rule

If a new page is functionally similar to:

- `Матеріали → Виробники`
- `Матеріали → Постачальники`
- `Фурнітура → Виробники`

first reuse their shared layout contract.

Do not create a "new design" for every tab.

## 15. Regression tests

If the layout contract changes, add regression tests for:

- shared page shell
- natural content height
- header actions placement
- breadcrumb
- no duplicate title
- action button pattern
- logo renderer
- no `window.confirm()` for new delete flows

## Notes

1. Check whether there is already a README, developer doc, or contributing guide where a short link to this standard belongs.
2. If such a place exists, add only a short link to `docs/admin-ui-standards.md`.
3. Do not rewrite other documentation.
4. Do not change production code.
