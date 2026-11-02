import Mathlib
namespace MathesisPilot
theorem lean_nat_dvd_trans : ∀ (a b c : Nat), a ∣ b → b ∣ c → a ∣ c := by
  intro a
  intro b
  intro c
  intro h1
  intro h2
  have h : a ∣ c := dvd_trans h1 h2
  exact h
end MathesisPilot
