import Mathlib
namespace MathesisHard
theorem lean_logic_serial_transitive_finite_refl : ∀ (α : Type) [Finite α] [Nonempty α] (R : α → α → Prop), (∀ x, ∃ y, R x y) → (∀ x y z, R x y → R y z → R x z) → ∃ x, R x x := by
  intro α _ _ R hs ht
  choose f hf using hs
  obtain ⟨a⟩ := ‹Nonempty α›
  have key : ∀ i k : ℕ, R (f^[i] a) (f^[i + k + 1] a) := by
    intro i k
    induction k with
    | zero => simpa [Function.iterate_succ_apply'] using hf (f^[i] a)
    | succ k ih =>
      have h2 := hf (f^[i + k + 1] a)
      rw [show i + (k + 1) + 1 = (i + k + 1) + 1 by ring, Function.iterate_succ_apply']
      exact ht _ _ _ ih h2
  obtain ⟨i, j, hij, heq⟩ := Finite.exists_ne_map_eq_of_infinite (fun n : ℕ => f^[n] a)
  rcases lt_or_gt_of_ne hij with h | h
  · obtain ⟨k, rfl⟩ := Nat.exists_eq_add_of_lt h
    have := key i k
    rw [← heq] at this
    exact ⟨_, this⟩
  · obtain ⟨k, rfl⟩ := Nat.exists_eq_add_of_lt h
    have := key j k
    rw [heq] at this
    exact ⟨_, this⟩
end MathesisHard
