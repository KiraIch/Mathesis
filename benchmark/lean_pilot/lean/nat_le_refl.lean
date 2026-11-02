namespace MathesisPilot
theorem lean_nat_le_refl : ∀ (n : Nat), n ≤ n := by
  intro n
  exact Nat.le_refl n
end MathesisPilot
