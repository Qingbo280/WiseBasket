import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useFonts } from 'expo-font';
import { useState, type ComponentProps } from 'react';
import {
  Image,
  Alert,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  type ImageSourcePropType,
} from 'react-native';
import {
  priceCheckLocationFontAssets,
  priceCheckLocationTokens,
} from '../components/price-check/priceCheckLocationTokens';
import { BasketItemImage } from '../components/BasketItemImage';
import { cachedFoodImageSourceForBackendId } from '../data/foodAssetManifest';
import type { RecipeDetail, RecipeFood, RecipeIngredientQuantity } from '../services/recipeApi';

type IconName = ComponentProps<typeof MaterialCommunityIcons>['name'];
type IngredientChoice = 'have' | 'need';

type RecipeIngredient = RecipeIngredientQuantity & {
  foodId: string;
  id: string;
  name: string;
  required: boolean;
};

export interface RecipeDetailIngredientState {
  haveIngredientNames: readonly string[];
  otherIngredientNames: readonly string[];
}

export interface RecipeDetailScreenProps {
  initialIngredientState?: RecipeDetailIngredientState;
  onBack?: () => void;
  onHaveItemsAdded?: (items: readonly Pick<RecipeFood, 'canonical_food_id' | 'name'>[]) => Promise<void>;
  onIngredientStateChange?: (state: RecipeDetailIngredientState) => void;
  onNeedItemsAdded?: (items: readonly Pick<RecipeFood, 'canonical_food_id' | 'name'>[]) => void;
  recipe: RecipeDetail;
  recipeImageSource: ImageSourcePropType | null | undefined;
}

export function ingredientsFromRecipe(recipe: RecipeDetail): RecipeIngredient[] {
  return recipe.ingredients.map(({ food, required, ...quantity }) => ({
    foodId: food.canonical_food_id,
    id: food.canonical_food_id,
    name: food.name,
    required,
    ...quantity,
  }));
}

function IngredientTile({ ingredient }: { ingredient: RecipeIngredient }) {
  return (
    <View style={styles.ingredientTile}>
      <View style={styles.ingredientIcon}>
        <BasketItemImage
          imageSource={cachedFoodImageSourceForBackendId(ingredient.foodId)}
          name={ingredient.name}
          resizeMode="contain"
          style={styles.ingredientImage}
        />
      </View>
      <Text numberOfLines={1} style={styles.ingredientTileName}>{ingredient.name}</Text>
    </View>
  );
}

function RecipeHeroImage({ source }: { source: ImageSourcePropType | null | undefined }) {
  return source ? (
    <Image
      accessibilityElementsHidden
      resizeMode="cover"
      source={source}
      style={styles.heroImage}
    />
  ) : (
    <View accessibilityElementsHidden style={styles.heroPlaceholder}>
      <MaterialCommunityIcons color="#BFD9CE" name="bowl-mix-outline" size={72} />
    </View>
  );
}

function IngredientGroup({
  ingredients,
  subtitle,
  title,
}: {
  ingredients: readonly RecipeIngredient[];
  subtitle: string;
  title: string;
}) {
  return (
    <View style={styles.ingredientGroup}>
      <Text style={styles.groupTitle}>{title} ({ingredients.length})</Text>
      <Text style={styles.groupSubtitle}>{subtitle}</Text>
      <View style={styles.ingredientGrid}>
        {ingredients.map((ingredient) => <IngredientTile ingredient={ingredient} key={ingredient.id} />)}
      </View>
    </View>
  );
}

function RadioChoice({
  checked,
  label,
  onPress,
}: {
  checked: boolean;
  label: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityLabel={label}
      accessibilityRole="radio"
      accessibilityState={{ checked }}
      onPress={onPress}
      style={({ pressed }) => [styles.choiceButton, pressed && styles.pressed]}
    >
      <MaterialCommunityIcons
        color={checked ? COLORS.green : COLORS.radio}
        name={checked ? 'radiobox-marked' : 'radiobox-blank'}
        size={22}
      />
      <Text style={styles.choiceText}>{label}</Text>
    </Pressable>
  );
}

function IngredientCheckSheet({
  ingredients,
  isSaving,
  onApply,
  onClose,
  selectionById,
  setSelectionById,
}: {
  ingredients: readonly RecipeIngredient[];
  isSaving: boolean;
  onApply: () => void;
  onClose: () => void;
  selectionById: Readonly<Record<string, IngredientChoice | undefined>>;
  setSelectionById: (
    update: (current: Readonly<Record<string, IngredientChoice | undefined>>) => Record<string, IngredientChoice | undefined>,
  ) => void;
}) {
  const choose = (id: string, choice: IngredientChoice) => {
    setSelectionById((current) => ({
      ...current,
      [id]: current[id] === choice ? undefined : choice,
    }));
  };

  return (
    <Modal
      animationType="slide"
      onRequestClose={onClose}
      transparent
      visible
    >
      <View style={styles.modalBackdrop}>
        <Pressable accessibilityLabel="Close ingredient check" onPress={onClose} style={StyleSheet.absoluteFill} />
        <View style={styles.sheetCard}>
          <ScrollView
            contentContainerStyle={styles.sheetContent}
            showsVerticalScrollIndicator={false}
          >
            <View accessibilityElementsHidden style={styles.sheetHandle} />
            <View style={styles.sheetHeader}>
              <View style={styles.sheetHeaderCopy}>
                <Text accessibilityRole="header" style={styles.sheetTitle}>Check your ingredients</Text>
                <Text style={styles.sheetBody}>
                  Let us know what you already have and which items to add to your shopping list.
                </Text>
              </View>
              <Pressable
                accessibilityLabel="Close ingredient check"
                accessibilityRole="button"
                onPress={onClose}
                style={({ pressed }) => [styles.closeButton, pressed && styles.pressed]}
              >
                <MaterialCommunityIcons color={COLORS.deepTeal} name="close" size={28} />
              </Pressable>
            </View>

            <View style={styles.sheetRows}>
              {ingredients.map((ingredient) => (
                <View key={ingredient.id} style={styles.sheetRow}>
                  <View style={styles.sheetIngredientIcon}>
                    <BasketItemImage
                      imageSource={cachedFoodImageSourceForBackendId(ingredient.foodId)}
                      name={ingredient.name}
                      resizeMode="contain"
                      style={styles.sheetIngredientImage}
                    />
                  </View>
                  <Text numberOfLines={2} style={styles.sheetIngredientName}>{ingredient.name}</Text>
                  <RadioChoice
                    checked={selectionById[ingredient.id] === 'have'}
                    label="Have it"
                    onPress={() => choose(ingredient.id, 'have')}
                  />
                  <RadioChoice
                    checked={selectionById[ingredient.id] === 'need'}
                    label="Need it"
                    onPress={() => choose(ingredient.id, 'need')}
                  />
                </View>
              ))}
            </View>

            <Pressable
              accessibilityLabel="Add needed items to shopping list"
              accessibilityRole="button"
              disabled={isSaving}
              onPress={onApply}
              style={({ pressed }) => [styles.primaryButton, pressed && styles.pressed]}
            >
              <MaterialCommunityIcons color={COLORS.white} name="basket-outline" size={25} />
              <Text style={styles.primaryButtonText}>{isSaving ? 'Saving ingredients…' : 'Add needed items to shopping list'}</Text>
            </Pressable>
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

export function RecipeDetailScreen({
  initialIngredientState,
  onBack,
  onHaveItemsAdded,
  onIngredientStateChange,
  onNeedItemsAdded,
  recipe,
  recipeImageSource,
}: RecipeDetailScreenProps) {
  const [fontsLoaded] = useFonts(priceCheckLocationFontAssets);
  const recipeIngredients = ingredientsFromRecipe(recipe);
  const availableIngredientNames = new Set(recipe.available_ingredients.map((food) => food.name));
  const [haveIngredients, setHaveIngredients] = useState<readonly RecipeIngredient[]>(() => (
    initialIngredientState
      ? recipeIngredients.filter((ingredient) => initialIngredientState.haveIngredientNames.includes(ingredient.name))
      : recipeIngredients.filter((ingredient) => availableIngredientNames.has(ingredient.name))
  ));
  const [otherIngredients, setOtherIngredients] = useState<readonly RecipeIngredient[]>(() => (
    initialIngredientState
      ? recipeIngredients.filter((ingredient) => initialIngredientState.otherIngredientNames.includes(ingredient.name))
      : recipeIngredients.filter((ingredient) => !availableIngredientNames.has(ingredient.name))
  ));
  const [isCheckSheetOpen, setIsCheckSheetOpen] = useState(false);
  const [selectionById, setSelectionById] = useState<Record<string, IngredientChoice | undefined>>({});
  const [isSaving, setIsSaving] = useState(false);

  const handleApplySelections = async () => {
    if (isSaving) return;
    setIsSaving(true);
    try {
      const selectedHave = otherIngredients.filter((ingredient) => selectionById[ingredient.id] === 'have');
      const selectedNeed = otherIngredients.filter((ingredient) => selectionById[ingredient.id] === 'need');
      if (selectedHave.length > 0) {
        await onHaveItemsAdded?.(selectedHave.map((ingredient) => ({
          canonical_food_id: ingredient.foodId, name: ingredient.name,
        })));
      }
      const selectedHaveIds = new Set(selectedHave.map((ingredient) => ingredient.id));
      const nextHaveIngredients = [
        ...haveIngredients,
        ...selectedHave.filter((ingredient) => !haveIngredients.some((item) => item.id === ingredient.id)),
      ];
      const nextOtherIngredients = otherIngredients.filter((ingredient) => !selectedHaveIds.has(ingredient.id));

      setHaveIngredients(nextHaveIngredients);
      setOtherIngredients(nextOtherIngredients);
      onIngredientStateChange?.({
        haveIngredientNames: nextHaveIngredients.map((ingredient) => ingredient.name),
        otherIngredientNames: nextOtherIngredients.map((ingredient) => ingredient.name),
      });
      if (selectedNeed.length > 0) {
        onNeedItemsAdded?.(selectedNeed.map((ingredient) => ({
          canonical_food_id: ingredient.foodId, name: ingredient.name,
        })));
      }

      setSelectionById({});
      setIsCheckSheetOpen(false);
    } catch (error) {
      if (Platform.OS === 'web') {
        window.alert(`Ingredients could not be saved.\n${error instanceof Error ? error.message : 'Please try again.'}\nYour choices are kept. Close this message and try submitting again.`);
      } else {
        Alert.alert('Ingredients could not be saved', error instanceof Error ? error.message : 'Please try again.');
      }
    } finally {
      setIsSaving(false);
    }
  };

  if (!fontsLoaded) {
    return <View style={styles.fontLoading} />;
  }

  return (
    <View style={styles.screen}>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.hero}>
          <RecipeHeroImage source={recipeImageSource} />
          <Pressable
            accessibilityLabel="Back to Meal Ideas"
            accessibilityRole="button"
            onPress={onBack}
            style={({ pressed }) => [styles.heroBackButton, pressed && styles.pressed]}
          >
            <MaterialCommunityIcons color={COLORS.deepTeal} name="arrow-left" size={29} />
          </Pressable>
          <View style={styles.timeChip}>
            <MaterialCommunityIcons color={COLORS.deepTeal} name="clock-outline" size={17} />
            <Text style={styles.timeChipText}>20 min</Text>
          </View>
        </View>

        <View style={styles.recipeHeader}>
          <Text accessibilityRole="header" style={styles.pageTitle}>{recipe.name}</Text>
          <Text style={styles.pageSubtitle}>{recipe.description ?? 'Simple, tasty, and uses what you have.'}</Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Ingredients</Text>
          <IngredientGroup
            ingredients={haveIngredients}
            subtitle="Already recorded in your kitchen."
            title="From what you have"
          />
          <IngredientGroup
            ingredients={otherIngredients}
            subtitle="Not recorded in What You Have yet."
            title="Other ingredients"
          />
          <Pressable
            accessibilityLabel="Check what I have"
            accessibilityRole="button"
            onPress={() => setIsCheckSheetOpen(true)}
            style={({ pressed }) => [styles.checkButton, pressed && styles.pressed]}
          >
            <MaterialCommunityIcons color={COLORS.deepTeal} name="clipboard-check-outline" size={22} />
            <Text style={styles.checkButtonText}>Check what I have</Text>
          </Pressable>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>How to cook</Text>
          <View style={styles.stepsList}>
            {recipe.cooking_steps.map((step, index) => (
              <View key={step} style={styles.stepRow}>
                <View style={styles.stepNumber}>
                  <Text style={styles.stepNumberText}>{index + 1}</Text>
                </View>
                <Text style={styles.stepText}>{step}</Text>
              </View>
            ))}
          </View>
        </View>
      </ScrollView>

      {isCheckSheetOpen ? (
        <IngredientCheckSheet
          ingredients={otherIngredients}
          isSaving={isSaving}
          onApply={handleApplySelections}
          onClose={() => setIsCheckSheetOpen(false)}
          selectionById={selectionById}
          setSelectionById={setSelectionById}
        />
      ) : null}
    </View>
  );
}

const COLORS = {
  background: '#FEFDFA',
  deepTeal: '#012C2D',
  green: '#2D806B',
  muted: '#486264',
  paleGreen: '#EFF8F1',
  paleMint: '#F2F7F4',
  radio: '#6E7E7E',
  surface: '#FFFFFF',
  white: '#FFFFFF',
} as const;

const styles = StyleSheet.create({
  checkButton: {
    alignItems: 'center',
    backgroundColor: COLORS.paleGreen,
    borderRadius: 16,
    flexDirection: 'row',
    gap: 8,
    justifyContent: 'center',
    marginTop: 14,
    minHeight: 48,
    paddingHorizontal: 14,
  },
  checkButtonText: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 15,
    lineHeight: 20,
  },
  choiceButton: {
    alignItems: 'center',
    flexDirection: 'row',
    flexShrink: 0,
    gap: 4,
    minHeight: 48,
    width: 76,
  },
  choiceText: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 12,
    lineHeight: 16,
  },
  closeButton: {
    alignItems: 'center',
    height: 48,
    justifyContent: 'center',
    width: 48,
  },
  content: {
    paddingBottom: 34,
  },
  fontLoading: {
    backgroundColor: COLORS.background,
    flex: 1,
  },
  groupSubtitle: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 14,
    lineHeight: 19,
    marginTop: 2,
  },
  groupTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 20,
    lineHeight: 25,
  },
  hero: {
    height: 246,
    overflow: 'hidden',
    position: 'relative',
  },
  heroBackButton: {
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.9)',
    borderRadius: 24,
    height: 48,
    justifyContent: 'center',
    left: 14,
    position: 'absolute',
    top: 14,
    width: 48,
  },
  heroPlaceholder: {
    alignItems: 'center',
    backgroundColor: '#EAF4EF',
    flex: 1,
    justifyContent: 'center',
  },
  heroImage: {
    height: '100%',
    width: '100%',
  },
  ingredientGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    paddingTop: 12,
  },
  ingredientGroup: {
    backgroundColor: COLORS.surface,
    borderColor: '#DCEBE1',
    borderRadius: 18,
    borderWidth: 1,
    marginTop: 14,
    padding: 12,
  },
  ingredientIcon: {
    alignItems: 'center',
    backgroundColor: COLORS.paleMint,
    borderRadius: 14,
    height: 44,
    justifyContent: 'center',
    width: 44,
  },
  ingredientImage: {
    borderRadius: 14,
    height: 44,
    width: 44,
  },
  ingredientTile: {
    alignItems: 'center',
    flexBasis: '31%',
    flexGrow: 0,
    minWidth: 0,
  },
  ingredientTileName: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 12,
    lineHeight: 17,
    marginTop: 5,
    maxWidth: '100%',
  },
  modalBackdrop: {
    backgroundColor: 'rgba(1, 44, 45, 0.44)',
    flex: 1,
    justifyContent: 'flex-end',
  },
  pageSubtitle: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 18,
    lineHeight: 24,
    marginTop: 3,
  },
  pageTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.heading,
    fontSize: 30,
    lineHeight: 36,
  },
  pressed: {
    opacity: 0.8,
  },
  primaryButton: {
    alignItems: 'center',
    backgroundColor: COLORS.deepTeal,
    borderRadius: 17,
    flexDirection: 'row',
    gap: 10,
    justifyContent: 'center',
    marginTop: 18,
    minHeight: 56,
    paddingHorizontal: 14,
  },
  primaryButtonText: {
    color: COLORS.white,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 15,
    lineHeight: 20,
  },
  recipeHeader: {
    paddingHorizontal: 20,
    paddingTop: 16,
  },
  screen: {
    backgroundColor: COLORS.background,
    flex: 1,
  },
  section: {
    paddingHorizontal: 20,
    paddingTop: 24,
  },
  sectionTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 24,
    lineHeight: 30,
  },
  sheetBody: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 15,
    lineHeight: 21,
    marginTop: 7,
  },
  sheetCard: {
    backgroundColor: COLORS.surface,
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    maxHeight: '90%',
    overflow: 'hidden',
  },
  sheetContent: {
    paddingBottom: 28,
    paddingHorizontal: 20,
    paddingTop: 12,
  },
  sheetHandle: {
    alignSelf: 'center',
    backgroundColor: '#CBD9DE',
    borderRadius: 4,
    height: 6,
    marginBottom: 15,
    width: 62,
  },
  sheetHeader: {
    alignItems: 'flex-start',
    flexDirection: 'row',
    gap: 8,
  },
  sheetHeaderCopy: {
    flex: 1,
    minWidth: 0,
  },
  sheetIngredientIcon: {
    alignItems: 'center',
    backgroundColor: COLORS.paleMint,
    borderRadius: 12,
    height: 42,
    justifyContent: 'center',
    width: 42,
  },
  sheetIngredientImage: {
    borderRadius: 12,
    height: 42,
    width: 42,
  },
  sheetIngredientName: {
    color: COLORS.deepTeal,
    flex: 1,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 14,
    lineHeight: 19,
    minWidth: 0,
  },
  sheetRows: {
    marginTop: 10,
  },
  sheetRow: {
    alignItems: 'center',
    borderBottomColor: '#E4ECE8',
    borderBottomWidth: 1,
    flexDirection: 'row',
    gap: 7,
    minHeight: 68,
  },
  sheetTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 24,
    lineHeight: 30,
  },
  stepsList: {
    gap: 14,
    paddingTop: 14,
  },
  stepNumber: {
    alignItems: 'center',
    backgroundColor: COLORS.paleGreen,
    borderRadius: 16,
    height: 32,
    justifyContent: 'center',
    width: 32,
  },
  stepNumberText: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 14,
    lineHeight: 18,
  },
  stepRow: {
    alignItems: 'flex-start',
    flexDirection: 'row',
    gap: 12,
  },
  stepText: {
    color: COLORS.muted,
    flex: 1,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 15,
    lineHeight: 21,
    minWidth: 0,
  },
  timeChip: {
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.94)',
    borderRadius: 17,
    bottom: 14,
    flexDirection: 'row',
    gap: 5,
    paddingHorizontal: 12,
    paddingVertical: 8,
    position: 'absolute',
    right: 14,
  },
  timeChipText: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 14,
    lineHeight: 18,
  },
});
