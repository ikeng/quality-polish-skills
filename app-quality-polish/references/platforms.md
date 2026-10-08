# Axis constraints (informative)

Normative content lives in `contract.yml` (PLT-01..07) and `platforms/<id>.yml`. This file
explains why each axis carries the constraints it does, and what typically fails.

## Two axes: platform and runtime

| Axis | kind | Meaning | Examples |
|---|---|---|---|
| Target platform | platform | Operating system or delivery surface | ios, android, harmonyos, web, h5, miniprogram, desktop |
| Runtime | runtime | Implementation framework that renders onto platforms | flutter, react-native |

**A runtime is not a platform.** Declaring `flutter` does not mean "we ship Flutter"; it
means "we accept Flutter's obligations on the platforms we do ship". A runtime profile
lists the platforms it can land on in `hosts`, and PLT-07 checks that `hosts` intersects
`targets`:

```
platforms: [ios, android] + runtime: flutter   -> PASS (flutter->android,ios)
platforms: [miniprogram] + runtime: flutter     -> FAIL (Flutter cannot run in a mini program)
platforms: [harmonyos]  + runtime: flutter      -> FAIL (mainline Flutter does not host HarmonyOS)
```

That last case is intentional. Shipping the Huawei or community fork to HarmonyOS is a
decision that must be recorded: add `harmonyos` to the profile's `hosts` and PLT-07 holds
you to it. Silently passing is not an option.

A project owes obligations only for the axes it declares. Adding an axis is additive: drop
in a profile, add an entry, and the existing clauses re-evaluate. Removing one must be a
deliberate edit to `platforms.yml`, recorded like any other contract change.

## Common rules

| Rule | Detail |
|---|---|
| Unit mapping | iOS `pt`, Android `dp`, HarmonyOS `vp`, Web/H5/desktop `px`, mini program `rpx`, Flutter/RN `logical_px`; PLT-02 checks against the profile |
| Threshold direction | The key name is the semantics: `_min` is a floor (project value >= profile), `_max` is a ceiling (project value <= profile), neither means it must be declared but is not numerically compared; PLT-04 checks |
| Capability declaration | Every capability in a profile must be declared in `platforms.yml` as `implemented` + `where`, or `not_applicable` + `reason`; PLT-03 checks |
| Runtime landing | A runtime's `hosts` must intersect `targets`; PLT-07 checks |
| Per-axis evidence | Visual baselines and device matrices are retained per axis; PLT-05 and PLT-06 |

## iOS (pt)

| Capability | Constraint | Typical failure |
|---|---|---|
| safe_area | Notch, Dynamic Island and Home Indicator safe areas | Bottom button crushed by the Home Indicator |
| dynamic_type | Dynamic Type semantic styles that do not clip at maximum size | Fixed font sizes truncate text |
| reduce_motion | Honour the Reduce Motion setting | Large translate or scale animations still run |
| semantic_dark | Semantic colours in dark mode, never naive inversion | Glaring white cards, distorted inverted images |
| haptics | Declared trigger points with a global opt-out | Every tap vibrates and cannot be disabled |
| swipe_back | System interactive pop gesture remains available | A custom carousel swallows the edge swipe |
| voiceover | accessibilityLabel everywhere, focus order follows reading order | Icon buttons announced as a meaningless "button" |

Thresholds: touch target at least 44pt, body text at least 17pt, contrast at least 4.5,
non-loop motion at most 350ms, dynamic type max scale at least 2.0.

## Android (dp)

| Capability | Constraint | Typical failure |
|---|---|---|
| insets_edge_to_edge | Edge-to-edge with status bar, navigation bar and IME insets | Content covered by the gesture pill, keyboard hides the input |
| sp_text | Text in sp so it scales; dp for text is forbidden | Text does not grow at the largest font setting |
| predictive_back | System back gesture and predictive back | Back gesture stops working, user is trapped |
| dynamic_color | Material You policy or an explicit fixed brand palette | Insufficient contrast on a dark wallpaper |
| ripple_focus | Ripple plus a visible focus indicator, including external keyboards | No tap feedback, or iOS-style press on a platform expecting ripple |
| talkback | Complete contentDescription, decorative elements non-focusable | TalkBack reads decorative images |

Thresholds: touch target at least 48dp, body text at least 14sp, contrast at least 4.5,
font scale max at least 2.0.

Variance across OEM ROMs (stock, Xiaomi, Huawei, OPPO) must be covered in the device
matrix; testing stock only is not coverage.

## HarmonyOS (vp)

HarmonyOS NEXT is an independent app model (ArkTS/ArkUI), not a reskinned Android, which
is why it is its own platform profile.

| Capability | Constraint | Typical failure |
|---|---|---|
| avoid_area | Status bar, navigation bar, cutout and curved-edge safe areas via avoidArea or immersive windows | Content covered by the cutout or bottom navigation bar |
| vp_fp_units | Dimensions in vp, text in fp, scaling with the system font setting | Text truncated at a larger system font |
| semantic_resources_dark | Colour resources such as `$r('app.color.*')` with a dark qualifier directory | Glaring white surfaces in dark mode |
| hap_size_budget | HAP/HSP splitting and resource compression | Bundle exceeds the store limit |
| lazy_foreach | LazyForEach with a reusable data source; no deep large objects refreshing the tree | List scrolling drops frames |
| atomic_service_card | Refresh policy and size adaptation for atomic-service cards | The card never refreshes or is laid out wrong |
| accessibility_text | accessibilityText or accessibilityGroup, decorative elements out of focus | Screen readers announce only the component type |
| continuation_state | State and failure fallback for distributed continuation | State lost after continuing on another device |

Thresholds: touch target at least 48vp, contrast at least 4.5, main HAP at most 10MB,
cold start at most 1500ms, font scale max at least 2.0.

## Web (px, desktop browsers)

| Capability | Constraint | Typical failure |
|---|---|---|
| keyboard_nav | Tab-reachable, focus order matches visual order, modals trap focus | A custom dropdown cannot be operated by keyboard |
| visible_focus | Visible focus ring; `outline: none` with no replacement is forbidden | Keyboard users cannot see where they are |
| hover_state | Declared hover state so information is not press-only | Desktop users cannot predict clickability |
| reduced_motion | Honour `prefers-reduced-motion` | Vestibular-sensitive users forced through motion |
| semantic_html | Semantic elements, landmarks, labels, alt text | A soup of divs makes screen reader navigation impossible |
| cursor_semantics | pointer / not-allowed / grab semantics | Clickable elements show the default arrow |
| zoom_200 | No content lost at 200% zoom or a 320px viewport | Fixed-width containers clipped when zoomed |

Thresholds: contrast at least 4.5, CLS at most 0.1, LCP at most 2500ms, INP at most
200ms, zoom at least 200%.

## H5 (mobile web, in-app browsers)

H5 runs inside someone else's container. Most defects come from viewport, safe areas and
host differences rather than from the layout itself.

| Capability | Constraint | Typical failure |
|---|---|---|
| viewport_fit_cover | `viewport-fit=cover` in the viewport meta tag | Safe-area variables are always zero and adaptation silently does nothing |
| safe_area_insets | Use `env(safe-area-inset-*)` | A fixed bottom button is covered by the Home Indicator |
| dvh_not_vh | No `100vh` full-height layouts; use dvh/svh or a JS fallback | The address bar crops the first screen and causes stray scrolling |
| tap_highlight | Handle `-webkit-tap-highlight-color` and `touch-action` | Grey tap flash, 300ms delay, accidental double-tap zoom |
| no_sticky_hover | No retained hover on touch; isolate with `@media (hover: hover)` | A tapped button stays in its hover style forever |
| host_containers | Declare host coverage (WeChat, QQ, UC, system browsers) and handle their navigation bar and back behaviour | Sharing, back behaviour or host font scaling behave unexpectedly in WeChat |
| overscroll | Handle overscroll and rubber-band | The page bounces or a host pull-to-refresh interrupts the action |
| font_fallback | System fallback for custom fonts, non-blocking | FOIT: invisible text while the font loads |

Thresholds: input font size at least 16px (below this, iOS zooms the page on focus), tap
target at least 44px, first-screen budget at most 200KB.

## Mini program (rpx)

No DOM. Bottlenecks concentrate on package size, setData cost and host navigation-bar
constraints.

| Capability | Constraint | Typical failure |
|---|---|---|
| package_split | Main/subpackage boundaries plus preloading, first-screen assets only in the main package | Main package exceeds the limit, or first paint waits on a subpackage |
| setdata_batching | Batched setData with a bounded payload; no whole-object passback, no per-item setData in lists | Long lists drop frames continuously |
| rpx_adaptation | rpx on a 750 basis, or an explicit px strategy | Spacing ratios distort across device widths |
| capsule_safe_zone | Keep clear of the capsule button safe area | Title or button hidden behind the capsule |
| image_domain_whitelist | https images, whitelisted domains, failure placeholder | Every image is a white block; console reports an illegal domain |
| hover_class | `hover-class` instead of `:hover` | Taps give no feedback at all |
| virtual_list | Virtual list or recycling for long lists | Long lists stutter and go blank |
| theme_darkmode | darkmode plus theme.json or CSS variables | Glaring white surfaces in the system dark theme |
| api_abstraction | Abstraction layer for wx/my/tt | Porting requires replacing every API call |

Thresholds: main package at most 2048KB (WeChat limit), total package at most 20MB,
single setData payload at most 256KB, first-screen budget at most 200KB, tap target at
least 44px.

## Desktop (px)

No touch assumption, a resizable window instead of a fixed viewport, and the keyboard as a
first-class input. Most defects come from ignoring resize, focus and DPI.

| Capability | Constraint | Typical failure |
|---|---|---|
| keyboard_shortcuts | Menu bar and shortcuts including Cmd versus Ctrl; core tasks not mouse-only | Keyboard users cannot complete the task |
| window_resize | Minimum window size and per-breakpoint layout | Narrowing the window makes buttons disappear |
| focus_ring_visible | Visible focus ring with full Tab and Shift+Tab traversal | Keyboard users lose their position |
| dpi_scaling | HiDPI and multi-monitor scale factors (1x, 1.5x, 2x) | Blurry or misaligned on an external display |
| hover_cursor | Hover state and cursor semantics | No indication of clickability |
| context_menu_dragdrop | Right-click menu and file drag-and-drop with hover feedback and type rejection | Right-click does nothing; dropping a file gives no feedback |
| native_frame | Title bar strategy and window control safe area | Custom title bar overlaps system window controls |
| large_screen_density | Information density: maximum content width, row height | Body text runs edge to edge and becomes unreadable |
| multi_window | State isolation and restoration across windows | State leaks between windows |

Thresholds: click target at least 28px (pointer precision is higher, but smaller is hard
to hit), minimum window 800x600, zoom at least 200%, startup at most 2000ms.

## Flutter (runtime, logical_px)

Flutter paints the same widget tree onto iOS, Android, Web, H5 and desktop. Quality is
about the engine (frame budget, repaint scope) and about **not erasing the host
platform's feel**.

| Capability | Constraint | Typical failure |
|---|---|---|
| const_widgets | `const` static subtrees so setState does not rebuild everything | Scrolling jank, exploding rebuild counts |
| repaint_boundary | RepaintBoundary around frequently repainting regions | A local animation forces a full-screen repaint |
| media_query_insets | MediaQuery viewPadding and viewInsets for safe areas and the keyboard | Bottom buttons covered, keyboard hides the input |
| platform_adaptive | Adaptive Material/Cupertino: scroll physics, transitions, back gesture | Android transitions on iOS, which immediately feels foreign |
| image_decode_budget | cacheWidth, cacheHeight, precacheImage | Full-resolution decoding causes memory spikes and OOM |
| semantics_labels | Semantics for labels and focus order | Custom-painted components unreachable by screen readers |
| deferred_components | Deferred components, route-level lazy loading, first-package budget | First package too large; users abandon the download |
| no_channel_in_hot_path | No MethodChannel on scrolling or animation hot paths | Per-frame cross-platform messaging causes stutter |

Thresholds: UI thread at most 8ms per frame, raster thread at most 8ms per frame, jank
ratio at most 1%, release package at most 30MB, touch target at least 48 logical_px.

## React Native (runtime, logical_px)

JS drives native views. The characteristic defects are JS-thread stalls, list memory and
platform feel.

| Capability | Constraint | Typical failure |
|---|---|---|
| virtualized_lists | VirtualizedList or FlashList with keyExtractor and getItemLayout | Long lists balloon in memory and go blank |
| native_driver_animation | useNativeDriver or Reanimated on the UI thread; no per-frame setState | Animations freeze whenever JS is busy |
| pressable_feedback | Pressable with a pressed state and hitSlop | Small icons are hard to hit, taps give no feedback |
| safe_area_context | SafeAreaProvider and useSafeAreaInsets | Notch and bottom gesture bar cover content |
| accessibility_props | accessibilityLabel/Role/State, decorative elements non-focusable | Screen readers read out decorative elements |
| image_caching | FastImage, prefetch, resizeMode; no original files | List images flicker, memory spikes |
| architecture_state | Fabric/TurboModules migration state, or a stated reason to stay behind | An architecture upgrade requires a full rewrite |
| startup_budget | Bundle size and first-render budget with Hermes and inline requires | Cold start shows a white screen for too long |

Thresholds: JS frame budget at most 16ms, bundle at most 1500KB, touch target at least 44
logical_px.

## Setting thresholds for a multi-axis project

1. **Pick the primary axis.** Its profile values become the design baseline in
   `design-token.json`.
2. **Other axes are floors.** No axis may go below its own profile.
3. **Make differences explicit.** An axis may be stricter (Android's 48dp is stricter than
   iOS's 44pt) but never looser.
4. **Share, do not copy.** Share semantic tokens; resolve unit conversion and axis-specific
   constraints in the profile or platform layer, never with `if (platform === ...)` in
   business code.
5. **A runtime stacks, it does not replace.** Using Flutter is not "two platforms instead
   of three"; it is accepting iOS, Android and Flutter obligations on one implementation.
   Three sets of obligations buy one codebase, and that trade should be made knowingly.
6. **Evidence per axis.** Visual baselines and device matrices are per-axis evidence
   clauses; reusing one screenshot set across axes is not evidence.
