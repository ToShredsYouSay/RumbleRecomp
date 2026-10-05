// RumbleRecomp: native versions of the game's hottest 3D matrix routines, compiled into the
// recompiled game module (RECOMPCORE_MODULE_EXTRA_SOURCES) and installed as DolRecomp
// replacement hooks ("ADDR:=function" in hooks.txt).
//
// Why: in a crowded fight (a Battle Royale with the randomizer has dozens of different
// characters on screen) the game spends a large share of its time multiplying 3x4 matrices
// for animation. The recompiled versions of these routines run every paired-single
// instruction through the emulator's fully general maths helpers (NaN handling, exception
// flags, register file in memory), which costs many times the work itself.
//
// Each routine here gives bit-identical results to the recompiled code. It reads and writes
// guest memory in the same order, with the same conversions, and does every multiply and
// fused multiply-add in the same order with the same rounding rules as GXRuntime's
// interpreter (operand c rounded to 25 bits, single-precision tie correction, results
// rounded to single, flushed to zero in non-IEEE mode). Anything unusual (a NaN or
// infinity in the inputs, quantised paired-single loads, or the FPU switched off) returns
// 0, and the original guest code runs instead. Only scratch registers are left different;
// the routines are ordinary SDK leaf functions, so no caller reads those.
//
// Setting RR_NATIVE_VERIFY=1 runs both: the native result is computed but not written, the
// guest code runs, and a hook on its return instruction compares the two. Mismatches are
// counted and the first few are printed to RR_NATIVE_VERIFY_LOG (or stderr).

#include "core/cpu.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define FPSCR_NI 0x00000004u
#define FPRF_SHIFT 12

// --- Exact replicas of the GXRuntime arithmetic (cpu_interpreter_float.c) ---------------

static inline unsigned lz64(u64 value)
{
    unsigned count = 0;
    while ((value & 0x8000000000000000ull) == 0) {
        value <<= 1;
        count++;
    }
    return count;
}

// force_25bit_c: the multiplier operand keeps 25 significant bits, rounded.
static inline f64 f25(f64 d)
{
    u64 integral = f64_bits(d);
    u64 exponent = integral & 0x7FF0000000000000ull;
    u64 fraction = integral & 0x000FFFFFFFFFFFFFull;
    if (exponent == 0 && fraction != 0) {
        s64 keep_mask = (s64)0xFFFFFFFFF8000000ll;
        u64 round = 0x8000000u;
        unsigned shift = lz64(fraction) - 11u;
        keep_mask >>= shift;
        round >>= shift;
        integral = (integral & (u64)keep_mask) + (integral & round);
    } else {
        integral = (integral & 0xFFFFFFFFF8000000ull) + (integral & 0x8000000ull);
    }
    return f64_value(integral);
}

// ni_madd_msub(a, c, b, sub=false, single=true) for finite inputs.
static inline f64 madd_single(f64 a, f64 c, f64 b)
{
    f64 c_round = f25(c);
    f64 value = fma(a, c_round, b);
    u64 bits = f64_bits(value);
    if ((bits & 0x000000001FFFFFFFull) == 0x0000000010000000ull) {
        f64 a_prime = b - value;
        f64 b_prime = value + a_prime;
        f64 error = fma(a, c_round, a_prime) + (b - b_prime);
        if (error != 0.0)
            value = f64_value((error > 0.0) == (value > 0.0) ? bits + 1 : bits - 1);
    }
    return value;
}

// force_single: FPSCR[NI] (non-IEEE mode, which this game runs in) flushes anything below the
// smallest normal single to a signed zero before rounding. s_ni is set from FPSCR on entry
// to each native routine; the module runs on one CPU thread.
static int s_ni;

static inline f64 rs(f64 value)
{
    if (s_ni) {
        u64 bits = f64_bits(value);
        if ((bits & 0x7FFFFFFFFFFFFFFFull) < 0x3810000000000000ull) {
            u32 flushed = (u32)((bits & 0x8000000000000000ull) >> 32);
            f32 zero;
            memcpy(&zero, &flushed, sizeof(zero));
            return (f64)zero;
        }
    }
    return (f64)(f32)value;
}

static inline f64 muls(f64 a, f64 c) { return rs(a * f25(c)); }
static inline f64 madds(f64 a, f64 c, f64 b) { return rs(madd_single(a, c, b)); }
static inline f64 adds(f64 a, f64 b) { return rs(a + b); }

static inline u32 classify_single(f64 value)
{
    f32 f = (f32)value;
    u32 bits;
    memcpy(&bits, &f, sizeof(bits));
    u32 sign = bits >> 31;
    u32 exponent = bits & 0x7F800000u;
    u32 fraction = bits & 0x007FFFFFu;
    if (exponent == 0x7F800000u)
        return fraction ? 0x11u : (sign ? 0x09u : 0x05u);
    if (exponent == 0)
        return fraction ? (sign ? 0x18u : 0x14u) : (sign ? 0x12u : 0x02u);
    return sign ? 0x08u : 0x04u;
}

static inline int finite_value(f64 value)
{
    return (f64_bits(value) & 0x7FF0000000000000ull) != 0x7FF0000000000000ull;
}

// --- Guest memory, the same way the generated code reaches it ---------------------------

// psq_l / psq_st with GQR0 = plain singles (the only case taken natively).
static inline f64 psq_value(CPUState* ctx, u32 ea)
{
    return f64_value(convert_to_double(mem_read32(ctx, ea)));
}

static inline u32 psq_bits(f64 value)
{
    return convert_to_single_ftz(f64_bits(value));
}

// lfs
static inline f64 lfs_value(CPUState* ctx, u32 ea)
{
    u64 x = mem_read32(ctx, ea);
    u64 exp = (x >> 23) & 0xFFu;
    u64 frac = x & 0x007FFFFFu;
    u64 result;
    if (exp > 0 && exp < 255) {
        u64 y = !(exp >> 7);
        u64 z = (y << 61) | (y << 60) | (y << 59);
        result = ((x & 0xC0000000u) << 32) | z | ((x & 0x3FFFFFFFu) << 29);
    } else if (exp == 0 && frac != 0) {
        exp = 1023 - 126;
        do {
            frac <<= 1;
            exp -= 1;
        } while ((frac & 0x00800000u) == 0);
        result = ((x & 0x80000000u) << 32) | (exp << 52) | ((frac & 0x007FFFFFu) << 29);
    } else {
        u64 y = exp >> 7;
        u64 z = (y << 61) | (y << 60) | (y << 59);
        result = ((x & 0xC0000000u) << 32) | z | ((x & 0x3FFFFFFFu) << 29);
    }
    return f64_value(result);
}

// Native paths are only taken in the state every running game is in: FPU on, IEEE mode,
// GQR0 unquantised for loads and stores, and paired-single loads enabled.
static inline int plain_state(const CPUState* ctx)
{
    s_ni = (ctx->fpscr & FPSCR_NI) != 0;
    return (ctx->msr & PPC_MSR_FP) &&
           (ctx->hid2 & PPC_HID2_LSQE) && (ctx->gqr[0] & 0x00070007u) == 0;
}

static inline void set_fprf(CPUState* ctx, f64 value)
{
    ctx->fpscr = (ctx->fpscr & ~(0x1Fu << FPRF_SHIFT)) | (classify_single(value) << FPRF_SHIFT);
}

// --- Output: written straight to guest memory, or recorded for RR_NATIVE_VERIFY ----------

enum { VERIFY_MAX = 12 * 64 };
typedef struct {
    int active;
    const char* name;
    u32 count;
    u32 addr[VERIFY_MAX];
    u32 value[VERIFY_MAX];
    u32 fpscr;
} Pending;

static int s_verify = -1;
static Pending s_pending;
static unsigned long long s_checked, s_mismatched, s_skipped, s_started;

// Verify output goes to RR_NATIVE_VERIFY_LOG (a file) when set, else stderr.
static FILE* log_file(void)
{
    static FILE* f;
    if (!f) {
        const char* path = getenv("RR_NATIVE_VERIFY_LOG");
        f = path && *path ? fopen(path, "a") : NULL;
        if (!f)
            f = stderr;
    }
    return f;
}

static inline int verifying(void)
{
    if (s_verify < 0) {
        const char* v = getenv("RR_NATIVE_VERIFY");
        s_verify = v && *v == '1';
    }
    return s_verify;
}

typedef struct {
    CPUState* ctx;
    Pending* pending;  // NULL: write to guest memory
} Out;

static inline void put(Out* out, u32 ea, u32 bits)
{
    if (!out->pending) {
        mem_write32(out->ctx, ea, bits);
        return;
    }
    if (out->pending->count < VERIFY_MAX) {
        out->pending->addr[out->pending->count] = ea;
        out->pending->value[out->pending->count] = bits;
    }
    out->pending->count++;
}

static inline void put_pair(Out* out, u32 ea, f64 ps0, f64 ps1)
{
    put(out, ea, psq_bits(ps0));
    put(out, ea + 4, psq_bits(ps1));
}

static void report(void)
{
    if (s_checked && (s_checked & (s_checked - 1)) == 0)  // at powers of two
    {
        fprintf(log_file(), "[native-mtx] started %llu checked %llu mismatched %llu skipped %llu\n",
                s_started, s_checked, s_mismatched, s_skipped);
        fflush(log_file());
    }
}

static void note_declined(const CPUState* ctx)
{
    static unsigned long long declined;
    declined++;
    if ((declined & (declined - 1)) == 0) {
        fprintf(log_file(), "[native-mtx] declined %llu (msr %08x fpscr %08x hid2 %08x gqr0 %08x)\n",
                declined, ctx->msr, ctx->fpscr, ctx->hid2, ctx->gqr[0]);
        fflush(log_file());
    }
}

// The verify hook on the guest routine's return: compare what it wrote with the native result.
static void verify_return(CPUState* ctx, const char* name)
{
    Pending* p = &s_pending;
    if (!p->active || p->name != name)
        return;
    p->active = 0;
    if (p->count > VERIFY_MAX) {
        s_skipped++;
        return;
    }
    int bad = (ctx->fpscr & (0x1Fu << FPRF_SHIFT)) != (p->fpscr & (0x1Fu << FPRF_SHIFT));
    for (u32 i = 0; i < p->count && !bad; i++)
        bad = mem_read32(ctx, p->addr[i]) != p->value[i];
    s_checked++;
    if (bad && ++s_mismatched <= 20) {
        fprintf(log_file(), "[native-mtx] MISMATCH in %s (call %llu)\n", name, s_checked);
        for (u32 i = 0; i < p->count; i++) {
            u32 got = mem_read32(ctx, p->addr[i]);
            if (got != p->value[i])
                fprintf(log_file(), "  %08x: guest %08x native %08x\n", p->addr[i], got, p->value[i]);
        }
        fprintf(log_file(), "  fpscr guest %08x native %08x\n", ctx->fpscr, p->fpscr);
        fflush(log_file());
    }
    report();
}

// Run a native routine: for real, or (verify mode) into the pending record, returning 0 so
// the guest code runs too.
#define RUN_NATIVE(NAME, BODY_CALL)                                                       \
    do {                                                                                  \
        if (!plain_state(ctx)) {                                                          \
            if (verifying())                                                              \
                note_declined(ctx);                                                       \
            return 0;                                                                     \
        }                                                                                 \
        if (!verifying()) {                                                               \
            Out out = {ctx, NULL};                                                        \
            return BODY_CALL;                                                             \
        }                                                                                 \
        s_pending.active = 0;                                                             \
        s_pending.count = 0;                                                              \
        s_pending.name = NAME;                                                            \
        u32 saved_gpr[32];                                                                \
        memcpy(saved_gpr, ctx->gpr, sizeof(saved_gpr));                                   \
        const u32 saved_fpscr = ctx->fpscr, saved_ctr = ctx->ctr;                         \
        const s64 saved_downcount = ctx->downcount;                                       \
        Out out = {ctx, &s_pending};                                                      \
        if (BODY_CALL) {                                                                  \
            s_pending.fpscr = ctx->fpscr;                                                 \
            s_pending.active = 1;                                                         \
            s_started++;                                                                  \
        }                                                                                 \
        memcpy(ctx->gpr, saved_gpr, sizeof(saved_gpr));                                   \
        ctx->fpscr = saved_fpscr;                                                         \
        ctx->ctr = saved_ctr;                                                             \
        ctx->downcount = saved_downcount;                                                 \
        return 0;                                                                         \
    } while (0)

// --- PSMTXIdentity (0x802C8A80) ----------------------------------------------------------
// r3 = matrix. Zero and one come from the game's constant pool (r2 - 0x69CC / - 0x69D0).

static int identity(CPUState* ctx, Out* out)
{
    const u32 m = ctx->gpr[3];
    const f64 zero = lfs_value(ctx, ctx->gpr[2] - 0x69CC);
    const f64 one = lfs_value(ctx, ctx->gpr[2] - 0x69D0);
    put_pair(out, m + 0x08, zero, zero);
    put_pair(out, m + 0x18, zero, zero);
    put_pair(out, m + 0x20, zero, zero);
    put_pair(out, m + 0x10, zero, one);
    put_pair(out, m + 0x00, one, zero);
    put_pair(out, m + 0x28, one, zero);
    return 1;
}

static const char k_identity[] = "PSMTXIdentity";
int rr_native_mtx_identity(CPUState* ctx) { RUN_NATIVE(k_identity, identity(ctx, &out)); }
void rr_verify_mtx_identity(CPUState* ctx) { verify_return(ctx, k_identity); }

// --- PSMTXCopy (0x802C8AB0) --------------------------------------------------------------
// r3 = source, r4 = destination; pair by pair, load then store.

static int copy(CPUState* ctx, Out* out)
{
    const u32 src = ctx->gpr[3], dst = ctx->gpr[4];
    for (u32 off = 0; off < 0x30; off += 8) {
        if (!out->pending) {
            const u32 a = psq_bits(psq_value(ctx, src + off));
            const u32 b = psq_bits(psq_value(ctx, src + off + 4));
            mem_write32(ctx, dst + off, a);
            mem_write32(ctx, dst + off + 4, b);
        } else {
            // A copy onto itself or a partial overlap reads what the previous pair wrote.
            // Verify mode cannot see those writes, so only compare non-overlapping copies.
            if (dst < src + 0x30 && src < dst + 0x30 && dst != src)
                return 0;
            put_pair(out, dst + off, psq_value(ctx, src + off), psq_value(ctx, src + off + 4));
        }
    }
    return 1;
}

static const char k_copy[] = "PSMTXCopy";
int rr_native_mtx_copy(CPUState* ctx) { RUN_NATIVE(k_copy, copy(ctx, &out)); }
void rr_verify_mtx_copy(CPUState* ctx) { verify_return(ctx, k_copy); }

// --- Shared 3x4 product --------------------------------------------------------------------
// Loads matrix rows as the guest does (pairs of singles) and checks they are all finite.

typedef struct {
    f64 v[3][4];
} Mtx34;

static inline int load_mtx(CPUState* ctx, u32 m, Mtx34* out)
{
    int ok = 1;
    for (int r = 0; r < 3; r++)
        for (int c = 0; c < 4; c++) {
            out->v[r][c] = psq_value(ctx, m + (u32)(r * 16 + c * 4));
            ok &= finite_value(out->v[r][c]);
        }
    return ok;
}

// One output row of A x B, in the guest's operation order. The translation column adds
// k0 * (lane 0 multiplier) and k1 * a[3]; PSMTXConcat uses a[3] for both lanes
// (ps_madds1), PSMTXConcatArray uses a[2] for lane 0 (ps_madd).
static inline void concat_row(const f64 a[4], const Mtx34* b, f64 k0, f64 k1, f64 k_lane0_mul,
                              f64 out[4])
{
    for (int j = 0; j < 4; j++) {
        f64 t = muls(b->v[0][j], a[0]);
        t = madds(b->v[1][j], a[1], t);
        t = madds(b->v[2][j], a[2], t);
        if (j == 2)
            t = madds(k0, k_lane0_mul, t);
        else if (j == 3)
            t = madds(k1, a[3], t);
        out[j] = t;
    }
}

// --- PSMTXConcat (0x802C8AF0) ----------------------------------------------------------------
// r3 = A, r4 = B, r5 = A x B. Every input is read before the first store, so the output may
// alias either input. The (0, 1) pair comes from 0x804B8B18.

static int concat(CPUState* ctx, Out* out)
{
    const u32 a_addr = ctx->gpr[3], b_addr = ctx->gpr[4], ab = ctx->gpr[5];
    Mtx34 a, b;
    if (!load_mtx(ctx, a_addr, &a) || !load_mtx(ctx, b_addr, &b))
        return 0;
    const f64 k0 = psq_value(ctx, 0x804B8B18), k1 = psq_value(ctx, 0x804B8B1C);
    if (!finite_value(k0) || !finite_value(k1))
        return 0;
    f64 r[3][4];
    for (int i = 0; i < 3; i++)
        concat_row(a.v[i], &b, k0, k1, a.v[i][3], r[i]);
    for (int i = 0; i < 3; i++) {
        put_pair(out, ab + (u32)(i * 16), r[i][0], r[i][1]);
        put_pair(out, ab + (u32)(i * 16 + 8), r[i][2], r[i][3]);
    }
    ctx->gpr[6] = 0x804B8B18;
    set_fprf(ctx, r[2][2]);  // last op: row 2, columns 2-3
    return 1;
}

static const char k_concat[] = "PSMTXConcat";
int rr_native_mtx_concat(CPUState* ctx) { RUN_NATIVE(k_concat, concat(ctx, &out)); }
void rr_verify_mtx_concat(CPUState* ctx) { verify_return(ctx, k_concat); }

// --- PSMTXConcatArray (0x802C8BC0) -----------------------------------------------------------
// r3 = A, r4 = array of B, r5 = array of A x B, r6 = count. Each B is read in full before its
// product is stored, so the arrays may be the same (in place). The (0, 1) pair comes from
// r13 - 0x4F08.

static int concat_array(CPUState* ctx, Out* out)
{
    const u32 a_addr = ctx->gpr[3], count = ctx->gpr[6];
    u32 src = ctx->gpr[4], dst = ctx->gpr[5];
    // The guest loop runs count - 1 times through bdnz, so it needs at least two matrices.
    if (count < 2 || count > 1024)
        return 0;
    Mtx34 a, b;
    if (!load_mtx(ctx, a_addr, &a))
        return 0;
    const u32 k_addr = ctx->gpr[13] - 0x4F08;
    const f64 k0 = psq_value(ctx, k_addr), k1 = psq_value(ctx, k_addr + 4);
    if (!finite_value(k0) || !finite_value(k1))
        return 0;
    // Check every source first, so a NaN anywhere leaves the whole call to the guest.
    for (u32 n = 0; n < count; n++)
        if (!load_mtx(ctx, src + n * 0x30, &b))
            return 0;
    // In place is fine; any other overlap depends on the guest loop's exact interleaving.
    if (dst < src + count * 0x30 && src < dst + count * 0x30 && dst != src)
        return 0;
    f64 last = 0.0;
    for (u32 n = 0; n < count; n++, src += 0x30, dst += 0x30) {
        load_mtx(ctx, src, &b);
        f64 r[3][4];
        for (int i = 0; i < 3; i++)
            concat_row(a.v[i], &b, k0, k1, a.v[i][2], r[i]);
        for (int i = 0; i < 3; i++) {
            put_pair(out, dst + (u32)(i * 16), r[i][0], r[i][1]);
            put_pair(out, dst + (u32)(i * 16 + 8), r[i][2], r[i][3]);
        }
        last = r[2][2];
    }
    ctx->gpr[0] = count - 1;
    ctx->gpr[4] += (count - 1) * 0x30;
    ctx->gpr[5] += (count - 1) * 0x30;
    ctx->gpr[6] = k_addr;
    ctx->ctr = 0;
    ctx->downcount -= (s64)count * 40;
    set_fprf(ctx, last);  // last op: the final matrix's row 2, columns 2-3
    return 1;
}

static const char k_concat_array[] = "PSMTXConcatArray";
int rr_native_mtx_concat_array(CPUState* ctx) { RUN_NATIVE(k_concat_array, concat_array(ctx, &out)); }
void rr_verify_mtx_concat_array(CPUState* ctx) { verify_return(ctx, k_concat_array); }

// --- PSMTXMultVec (0x802C9590) ---------------------------------------------------------------
// r3 = matrix, r4 = source vector, r5 = destination vector. Each element is
// (m0 * x + m2 * z) + (m1 * y + m3 * 1), lane by lane, then the two lanes summed.

static int mult_vec(CPUState* ctx, Out* out)
{
    const u32 m = ctx->gpr[3], src = ctx->gpr[4], dst = ctx->gpr[5];
    const f64 x = psq_value(ctx, src), y = psq_value(ctx, src + 4), z = psq_value(ctx, src + 8);
    if (!finite_value(x) || !finite_value(y) || !finite_value(z))
        return 0;
    Mtx34 mm;
    if (!load_mtx(ctx, m, &mm))
        return 0;
    f64 r[3];
    for (int i = 0; i < 3; i++) {
        const f64 lane0 = madds(mm.v[i][2], z, muls(mm.v[i][0], x));
        const f64 lane1 = madds(mm.v[i][3], 1.0, muls(mm.v[i][1], y));
        r[i] = adds(lane0, lane1);
    }
    // The guest stores element 0 before it reads matrix row 2; a destination inside that
    // row would change what it reads. Leave that case to the guest.
    if (dst + 4 > m + 0x20 && dst < m + 0x30)
        return 0;
    for (int i = 0; i < 3; i++)
        put(out, dst + (u32)(i * 4), psq_bits(r[i]));
    set_fprf(ctx, r[2]);  // last op: ps_sum0 for element 2
    return 1;
}

static const char k_mult_vec[] = "PSMTXMultVec";
int rr_native_mtx_mult_vec(CPUState* ctx) { RUN_NATIVE(k_mult_vec, mult_vec(ctx, &out)); }
void rr_verify_mtx_mult_vec(CPUState* ctx) { verify_return(ctx, k_mult_vec); }
