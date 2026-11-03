import Mathlib
namespace MathesisHard
theorem lean_ineq_weighted_recip_36 : ∀ a b c : ℝ, 0 < a → 0 < b → 0 < c → a + b + c = 1 → 36 ≤ 1 / a + 4 / b + 9 / c := by
  intro a b c ha hb hc h
  have k : ∀ x m : ℝ, 0 < x → 0 < m → 2 / m - x / m ^ 2 ≤ 1 / x := by
    intro x m hx hm
    have : 1 / x - (2 / m - x / m ^ 2) = (x - m) ^ 2 / (x * m ^ 2) := by
      field_simp
      ring
    have h0 : 0 ≤ (x - m) ^ 2 / (x * m ^ 2) := by positivity
    linarith
  have h1 : 12 - 36 * a ≤ 1 / a := by
    have := k a (1 / 6) ha (by norm_num)
    have e : 2 / (1 / 6 : ℝ) - a / (1 / 6) ^ 2 = 12 - 36 * a := by ring
    linarith
  have h2 : 6 - 9 * b ≤ 1 / b := by
    have := k b (1 / 3) hb (by norm_num)
    have e : 2 / (1 / 3 : ℝ) - b / (1 / 3) ^ 2 = 6 - 9 * b := by ring
    linarith
  have h3 : 4 - 4 * c ≤ 1 / c := by
    have := k c (1 / 2) hc (by norm_num)
    have e : 2 / (1 / 2 : ℝ) - c / (1 / 2) ^ 2 = 4 - 4 * c := by ring
    linarith
  have e1 : 4 / b = 4 * (1 / b) := by ring
  have e2 : 9 / c = 9 * (1 / c) := by ring
  rw [e1, e2]
  linarith
end MathesisHard
