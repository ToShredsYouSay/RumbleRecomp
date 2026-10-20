// RumbleRecomp: widescreen HUD anchoring for Pokémon Rumble (WPSE01), compiled into the
// recompiled game module (RECOMPCORE_MODULE_EXTRA_SOURCES) and called from a DolRecomp
// instruction hook (DOLRECOMP_HOOKS=802A52F4:rr_hook_lyt_pane_translate).
//
// The game's HUD widgets are NW4R layouts drawn in a 648x480 orthographic space (x in
// -324..+324). Under Dolphin's widescreen hack the runtime keeps 2D in its original
// proportions (VertexShaderManager: centred 2D is compressed toward the screen centre by
// the widening factor), so widgets designed for a screen corner would end up floating
// inside a centred 16:9 area. This hook moves each corner widget's "root" pane outward by
// exactly the extra width, so it keeps its original distance from the real screen edge
// and its original size relative to the screen height, at any aspect ratio, and live
// as the window is resized.
//
// Hook point: nw4r::lyt::Pane::CalculateMtx (0x802A51A0) at 0x802A52F4, after it loads
// the pane's translation into f1 (x) and f2 (y) and before it builds the local matrix.
// Only the loaded register values change; the pane in guest memory is never written, so
// nothing accumulates across frames and animations stay intact.

#include "core/cpu.h"

#if defined(_WIN32)
#define RR_EXPORT __declspec(dllexport)
#else
#define RR_EXPORT __attribute__((visibility("default")))
#endif

// Layout units to add at the right (dx) / top (dy) screen edge. Set by the runtime
// every timing slice from the current widescreen factors; 0 = feature off.
static volatile float s_hud_dx = 0.0f;
static volatile float s_hud_dy = 0.0f;

RR_EXPORT void staticrecomp_set_hud_anchor(float dx, float dy)
{
    s_hud_dx = dx;
    s_hud_dy = dy;
}

// nw4r::lyt::Pane field offsets in this build (verified against a live RAM dump).
enum {
    PANE_PARENT = 0x0C,
    PANE_CHILD_COUNT = 0x10,
    PANE_CHILD_FIRST = 0x14,  // -> first child's list node (child + 4)
    PANE_NODE_NEXT = 0x04,    // this pane's list node: next node pointer
    PANE_NAME = 0xBC,
};

static int pane_name_is(CPUState* ctx, u32 pane, const char* name)
{
    for (u32 i = 0;; i++) {
        const u8 c = mem_read8(ctx, pane + PANE_NAME + i);
        if (c != (u8)name[i])
            return 0;
        if (c == 0)
            return 1;
    }
}

static u32 pane_child(CPUState* ctx, u32 pane, u32 index)
{
    if (mem_read32(ctx, pane + PANE_CHILD_COUNT) <= index)
        return 0;
    u32 node = mem_read32(ctx, pane + PANE_CHILD_FIRST);
    for (u32 i = 0; i < index && node; i++)
        node = mem_read32(ctx, node);
    return node ? node - 4u : 0;
}

// Which screen edge a HUD layout belongs to, identified by its root pane's children
// (names from the game's .brlyt files). +1 right, -1 left, 0 leave alone (centred
// dialogs, and HP bars / speech balloons that follow characters).
static int anchor_side(CPUState* ctx, u32 root)
{
    const u32 first = pane_child(ctx, root, 0);
    if (!first)
        return 0;
    // moneylife_root / money_root / life_root: the P counter and Wonder Keys panel.
    if (pane_name_is(ctx, first, "win_c"))
        return 1;
    // minimap
    if (pane_name_is(ctx, first, "map"))
        return 1;
    // combo counter (top right)
    if (pane_name_is(ctx, first, "combo"))
        return 1;
    // tutorial_window (bottom left): children "bk", "text"
    if (pane_name_is(ctx, first, "bk")) {
        const u32 second = pane_child(ctx, root, 1);
        if (second && pane_name_is(ctx, second, "text"))
            return -1;
    }
    return 0;
}

// ---------------------------------------------------------------------------------------
// Widen the game's own view-dependent maths to match Dolphin's widescreen hack.
//
// The hack widens the GPU projection only; the game still believes its camera is 16:9.
// Two consumers of the camera shape then disagree with what is on screen:
//  * nw4r::g3d GatherDrawScnObj builds the culling frustum (math::FRUSTUM::Set) from the
//    camera's fovy/aspect (or top/bottom/left/right), so models beyond the old 16:9 edge are
//    culled, so characters vanish or pop in at the old edge.
//  * nw4r::g3d Camera::GetProjectionTexMtx maps screen space onto textures for effects that
//    sample a copy of the framebuffer (e.g. the boss charge-up heat haze), so they sample the
//    wrong region: a visible square around the effect.
// These hooks widen the arguments to exactly those calls by the same factors the hack uses
// (dx/dy from staticrecomp_set_hud_anchor), and nothing else: the camera data itself, and
// every other reader of it (HUD placement, UI), are untouched.
//   Perspective (fovy in degrees in f1, aspect in f2):
//     0x80269DCC  GatherDrawScnObj -> FRUSTUM::Set(fovy, aspect, near, far, mtx)
//     0x80264FBC  GetProjectionTexMtx -> C_MTXLightPerspective(fovy, aspect, ...)
//   Frustum (top, bottom, left, right in f1..f4):
//     0x80269DF4  GatherDrawScnObj -> FRUSTUM::Set(t, b, l, r, near, far, mtx)
//     0x80264F94  GetProjectionTexMtx -> C_MTXLightFrustum(t, b, l, r, ...)

#include <math.h>

static void view_factors(float* kh, float* kv)
{
    *kh = 1.0f + s_hud_dx / 324.0f;
    *kv = 1.0f + s_hud_dy / 240.0f;
}

static void set_f(CPUState* ctx, int reg, float v)
{
    ctx->fpr[reg] = ctx->ps1[reg] = (f64)v;
}

void rr_hook_view_perspective(CPUState* ctx)
{
    float kh, kv;
    view_factors(&kh, &kv);
    if (kh == 1.0f && kv == 1.0f)
        return;
    const float fovy = (float)ctx->fpr[1];
    const float aspect = (float)ctx->fpr[2];
    if (fovy <= 0.0f || fovy >= 179.0f || aspect <= 0.0f)
        return;
    const float rad = 3.14159265f / 180.0f;
    // A taller view (kv) opens the vertical field of view; the horizontal extent must
    // then grow by kh relative to the new height, hence aspect * kh / kv.
    const float new_fovy = 2.0f * atanf(tanf(fovy * 0.5f * rad) * kv) / rad;
    set_f(ctx, 1, new_fovy);
    set_f(ctx, 2, aspect * kh / kv);
}

void rr_hook_view_frustum(CPUState* ctx)
{
    float kh, kv;
    view_factors(&kh, &kv);
    if (kh == 1.0f && kv == 1.0f)
        return;
    set_f(ctx, 1, (float)ctx->fpr[1] * kv);
    set_f(ctx, 2, (float)ctx->fpr[2] * kv);
    set_f(ctx, 3, (float)ctx->fpr[3] * kh);
    set_f(ctx, 4, (float)ctx->fpr[4] * kh);
}

// ---------------------------------------------------------------------------------------
// Native-aspect scenes. The "Pokémon You Have Befriended" results screen (gameresult.brlyt)
// and the Ranking screen (ranking.brlyt) are small 3D rooms with nothing built beyond their
// 16:9 walls. While one of their layouts is being laid out, raise a flag; the runtime polls
// it and has the presenter show that scene at 16:9 with blurred side panels.
static volatile int s_native_scene_seen = 0;

RR_EXPORT int staticrecomp_poll_native_scene(void)
{
    const int seen = s_native_scene_seen;
    s_native_scene_seen = 0;
    return seen;
}

static void detect_native_scene(CPUState* ctx, u32 root_pane)
{
    const u32 first = pane_child(ctx, root_pane, 0);
    const u32 second = pane_child(ctx, root_pane, 1);
    if (!first || !second)
        return;
    // gameresult.brlyt: TITLE, STRONGEST, NEW, Null_00, NEXT
    if (pane_name_is(ctx, first, "TITLE") && pane_name_is(ctx, second, "STRONGEST"))
        s_native_scene_seen = 1;
    // ranking.brlyt: P0, P1, P2, P3, TITLE_01, TITLE
    else if (pane_name_is(ctx, first, "P0") && pane_name_is(ctx, second, "P1")) {
        const u32 fifth = pane_child(ctx, root_pane, 4);
        if (fifth && pane_name_is(ctx, fifth, "TITLE_01"))
            s_native_scene_seen = 1;
    }
}

// battleroyal.brlyt has no "root" pane: its two widgets, ENEMY (Pokémon remaining) and
// TIME, hang directly off RootPane, both in the top-right corner.
static int battleroyal_side(CPUState* ctx, u32 pane, u32 root_pane)
{
    const u32 first = pane_child(ctx, root_pane, 0);
    const u32 second = pane_child(ctx, root_pane, 1);
    if (!first || !second || !pane_name_is(ctx, first, "ENEMY") || !pane_name_is(ctx, second, "TIME"))
        return 0;
    return (pane == first || pane == second) ? 1 : 0;
}

// Same detection, but at the top of Pane::CalculateMtx (0x802A51C8, r3 = pane), which runs for
// hidden panes too: the results/ranking rooms fade in for several frames before their layout's
// panes become visible, and those frames must already be shown at the native aspect.
void rr_hook_lyt_pane_enter(CPUState* ctx)
{
    const u32 pane = ctx->gpr[3];
    const u32 parent = mem_read32(ctx, pane + PANE_PARENT);
    if (parent && pane_name_is(ctx, parent, "RootPane"))
        detect_native_scene(ctx, parent);
}

void rr_hook_lyt_pane_translate(CPUState* ctx)
{
    const u32 pane = ctx->gpr[30];
    const u32 parent = mem_read32(ctx, pane + PANE_PARENT);
    if (!parent || !pane_name_is(ctx, parent, "RootPane"))
        return;
    // Runs for every visible top-level pane, so each frame a layout is on screen.
    detect_native_scene(ctx, parent);
    const float dx = s_hud_dx, dy = s_hud_dy;
    if (dx == 0.0f && dy == 0.0f)
        return;
    const int side = pane_name_is(ctx, pane, "root") ? anchor_side(ctx, pane)
                                                     : battleroyal_side(ctx, pane, parent);
    if (!side)
        return;
    // lfs loaded single-precision values into both paired-single lanes.
    const float x = (float)ctx->fpr[1] + (float)side * dx;
    const float y0 = (float)ctx->fpr[2];
    const float y = y0 + (y0 >= 0.0f ? dy : -dy);
    ctx->fpr[1] = ctx->ps1[1] = (f64)x;
    ctx->fpr[2] = ctx->ps1[2] = (f64)y;
}

// ---------------------------------------------------------------------------------------
// Full-width layout pieces: black.brlyt's backdrop behind the "Battle Royale" banner, the
// "You lose" / "Time up" windows, notice.brlyt's area-name bar and the like are drawn exactly
// one layout-width (656) wide, so under the widescreen HUD compression they only cover the
// centre 16:9 and the 3D scene shows at the sides. Widen those panes by the widescreen
// factor. Hook: nw4r::lyt::Pane::CalculateMtx at 0x802A5268, where f1/f2 hold the pane's
// scale for PSMTXScale; r30 = pane (translate at +0x2C, size at +0x4C).
// Only backdrops and bars (names from the game's .brlyt files): every layout's RootPane is also
// one layout-width wide, and so are some textured letters (e.g. the "Battle Royale" title),
// which must keep their shape.
enum { PANE_TRANSLATE_X = 0x2C, PANE_SIZE_W = 0x4C };

static int is_full_width_backdrop(CPUState* ctx, u32 pane)
{
    static const char* const names[] = {
        "bk", "bk_00", "bk_01", "bk_black", "Window_00", "tutorial_bk",           // dim/black backdrops
        "BAR_AREA", "bar_stage", "bar_clear", "bar_youwin",                         // notice.brlyt banners
        "bg_bar", "bg_bar_00", "bg_bar_01",                                         // rival.brlyt bands
        "bar", "grd",                          // boss preview: title bar, fire band (not extracted)
    };
    for (u32 i = 0; i < sizeof(names) / sizeof(names[0]); i++)
        if (pane_name_is(ctx, pane, names[i]))
            return 1;
    return 0;
}

// RR_LOG_WIDE_PANES=1: print each distinct name of a layout-wide, centred pane once (to find
// backdrops in layouts that are not in the extracted set).
#include <stdio.h>
#include <stdlib.h>
static void log_full_width_pane(CPUState* ctx, u32 pane)
{
    static int enabled = -1;
    static u32 seen[64];
    static int nseen = 0;
    if (enabled < 0)
        enabled = getenv("RR_LOG_WIDE_PANES") != NULL;
    if (!enabled || nseen >= 64)
        return;
    union { u32 u; float f; } w, tx;
    w.u = mem_read32(ctx, pane + PANE_SIZE_W);
    tx.u = mem_read32(ctx, pane + PANE_TRANSLATE_X);
    const float sx = (float)ctx->fpr[1];
    if (fabsf(w.f * sx) < 600.0f || fabsf(tx.f) > 8.0f)
        return;
    char name[17];
    u32 hash = 2166136261u;
    for (int i = 0; i < 16; i++) {
        name[i] = (char)mem_read8(ctx, pane + PANE_NAME + (u32)i);
        hash = (hash ^ (u8)name[i]) * 16777619u;
        if (!name[i])
            break;
    }
    name[16] = 0;
    for (int i = 0; i < nseen; i++)
        if (seen[i] == hash)
            return;
    seen[nseen++] = hash;
    const u32 parent = mem_read32(ctx, pane + PANE_PARENT);
    char pname[17] = {0};
    for (int i = 0; parent && i < 16; i++)
        if (!(pname[i] = (char)mem_read8(ctx, parent + PANE_NAME + (u32)i)))
            break;
    fprintf(stderr, "[wide-pane] %s w=%.0f sx=%.2f tx=%.1f parent=%s vtbl=%08X\n", name, w.f, sx, tx.f,
            pname, mem_read32(ctx, pane));
    fflush(stderr);
}

static int is_banner_picture(CPUState* ctx, u32 pane);  // "Battle Royale" banner, see below

void rr_hook_lyt_pane_scale(CPUState* ctx)
{
    float kh, kv;
    view_factors(&kh, &kv);
    if (kh <= 1.0f)
        return;
    const u32 pane = ctx->gpr[30];
    log_full_width_pane(ctx, pane);
    if (!is_full_width_backdrop(ctx, pane) && !is_banner_picture(ctx, pane))
        return;
    union { u32 u; float f; } w, tx;
    w.u = mem_read32(ctx, pane + PANE_SIZE_W);
    tx.u = mem_read32(ctx, pane + PANE_TRANSLATE_X);
    const float sx = (float)ctx->fpr[1];
    if (fabsf(w.f * sx) < 640.0f || fabsf(tx.f) > 8.0f)
        return;
    set_f(ctx, 1, sx * kh);
}

// ---------------------------------------------------------------------------------------
// "Battle Royale" start banner. Its black backdrop (Battle_Royalbase) and glow (kasan) are single pictures
// with the letters cut out, so widening them (rr_hook_lyt_pane_scale) would stretch the letters. Instead the
// texture coordinates are pulled in by the same factor around their centre for the draw, so the letters keep
// their shape and the extra width repeats the texture's edge (plain black). Hooks in Picture::DrawSelf:
//   0x802A7648  bl DrawQuad (r28 = Picture, r5 = texcoord sets, r6 = TexCoordData*): adjust, saving originals
//   0x802A764C  after DrawQuad returns (also reached when DrawSelf skips drawing): restore the originals
enum { PICTURE_TEXCOORD_COUNT = 0xE9, PICTURE_TEXCOORDS = 0xEC };

static int is_banner_picture(CPUState* ctx, u32 pane)
{
    const u32 parent = mem_read32(ctx, pane + PANE_PARENT);
    return parent && pane_name_is(ctx, parent, "main") &&
           (pane_name_is(ctx, pane, "Battle_Royalbase") || pane_name_is(ctx, pane, "kasan"));
}

static u32 s_uv_addr = 0;     // guest address of the adjusted texcoords (0 = nothing to restore)
static u32 s_uv_saved[4 * 8]; // up to 4 texcoord sets x 4 vertices x (u, v)
static u32 s_uv_count = 0;

void rr_hook_picture_draw(CPUState* ctx)
{
    float kh, kv;
    view_factors(&kh, &kv);
    const u32 pane = ctx->gpr[28];
    if (kh <= 1.0f || !is_banner_picture(ctx, pane))
        return;
    const u32 sets = mem_read8(ctx, pane + PICTURE_TEXCOORD_COUNT);
    const u32 addr = mem_read32(ctx, pane + PICTURE_TEXCOORDS);
    if (!addr || sets == 0 || sets > 4)
        return;
    s_uv_addr = addr;
    s_uv_count = sets * 8;
    for (u32 set = 0; set < sets; set++) {
        union { u32 u; float f; } uv[8];
        for (u32 i = 0; i < 8; i++)
            s_uv_saved[set * 8 + i] = uv[i].u = mem_read32(ctx, addr + (set * 8 + i) * 4);
        const float centre = (uv[0].f + uv[2].f + uv[4].f + uv[6].f) * 0.25f;
        for (u32 i = 0; i < 8; i += 2) {  // u of each vertex; v unchanged
            uv[i].f = centre + (uv[i].f - centre) * kh;
            mem_write32(ctx, addr + (set * 8 + i) * 4, uv[i].u);
        }
    }
}

void rr_hook_picture_drawn(CPUState* ctx)
{
    if (!s_uv_addr)
        return;
    for (u32 i = 0; i < s_uv_count; i++)
        mem_write32(ctx, s_uv_addr + i * 4, s_uv_saved[i]);
    s_uv_addr = 0;
}

// ---------------------------------------------------------------------------------------
// Weekend Edition wild-Pokémon randomizer (native port of the community Gecko code
// C2159AD0, see docs/reference/WEEKEND_RANDOMIZER_CHEAT.md). Hook at 0x80159AD0 inside
// NewPPD, immediately before `mr r28, r3` where r3 points at the spawn's entry in the
// 28-byte-stride table at 0x8035DF88. Unless the encounter is scripted (word at r30+0x20 ==
// 0x1752), replace r3 with a random entry. The launcher sets RUMBLE_RANDOMIZER to the entry
// count (556 = Weekend 1.5, 559 = Weekend 1.5 + PATCH1); unset or 0 = off. Uses a host RNG
// instead of the game's rand_fn_8019DEF0, so the game's own random sequence is untouched.
#include <stdlib.h>
#include <time.h>

void rr_hook_randomizer(CPUState* ctx)
{
    static int range = -1;
    static u32 state = 0;
    if (range < 0) {
        const char* v = getenv("RUMBLE_RANDOMIZER");
        range = v ? atoi(v) : 0;
        if (range < 0 || range > 4096)
            range = 0;
        state = (u32)time(NULL) ^ 0x9E3779B9u;
        if (!state)
            state = 1;
    }
    if (range == 0)
        return;
    if (mem_read32(ctx, ctx->gpr[30] + 0x20) == 0x1752)
        return;
    state ^= state << 13;
    state ^= state >> 17;
    state ^= state << 5;
    ctx->gpr[3] = 0x8035DF88u + (state % (u32)range) * 0x1Cu;
}
