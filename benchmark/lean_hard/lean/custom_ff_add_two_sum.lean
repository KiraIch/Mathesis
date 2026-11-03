import Mathlib
namespace MathesisHard
theorem lean_custom_ff_add_two_sum : ∀ f : ℕ → ℕ, (∀ n, f (f n) = n + 2) → f 0 + f 1 = 3 := by
  intro f h
  have h2 : ∀ n, f (n + 2) = f n + 2 := by
    intro n
    have := h (f n)
    rw [h n] at this
    exact this
  have h3 : ∀ k, f (2 * k) = f 0 + 2 * k ∧ f (2 * k + 1) = f 1 + 2 * k := by
    intro k
    induction k with
    | zero => simp
    | succ k ih =>
      obtain ⟨i1, i2⟩ := ih
      constructor
      · have := h2 (2 * k)
        rw [show 2 * (k + 1) = 2 * k + 2 by ring, this]
        omega
      · have := h2 (2 * k + 1)
        rw [show 2 * (k + 1) + 1 = 2 * k + 1 + 2 by ring, this]
        omega
  have ha := h 0
  have hb := h 1
  obtain ⟨p, hp | hp⟩ := Nat.even_or_odd' (f 0) <;>
  obtain ⟨q, hq | hq⟩ := Nat.even_or_odd' (f 1) <;>
  · have e1 := h3 p
    have e2 := h3 q
    rw [hp] at ha
    rw [hq] at hb
    omega
end MathesisHard
