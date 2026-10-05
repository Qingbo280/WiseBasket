import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useFonts } from 'expo-font';
import { useMemo, useState, type ComponentProps } from 'react';
import {
  Image,
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
import { recipeImageSourceForId } from '../data/recipeAssetManifest';

type IconName = ComponentProps<typeof MaterialCommunityIcons>['name'];
export type MealIdeasCategory = 'All' | 'Quick' | 'Stir-fry' | 'Soup' | 'Rice dish';

type RecipeIngredient = {
  icon: IconName;
  imageSource?: ImageSourcePropType | null;
  name: string;
};

export type MealIdea = {
  categories: readonly Exclude<MealIdeasCategory, 'All'>[];
  /** Full recipe count, separate from the two thumbnail previews below. */
  ingredientCount?: number;
  ingredients: readonly RecipeIngredient[];
  imageSource?: ImageSourcePropType | null;
  recipeId: string;
  tag: string;
  tagTone: 'blue' | 'green';
  time: string;
  title: string;
};

export const MEAL_IDEAS_CATEGORIES: readonly MealIdeasCategory[] = [
  'All',
  'Quick',
  'Stir-fry',
  'Soup',
  'Rice dish',
];

export interface MealIdeasScreenProps {
  onBack?: () => void;
  onRecipePress?: (recipe: MealIdea) => void;
  recipes?: readonly MealIdea[];
}

function RecipeImage({ recipe }: { recipe: MealIdea }) {
  return recipe.imageSource ? (
    <Image
      accessibilityElementsHidden
      resizeMode="cover"
      source={recipe.imageSource}
      style={styles.recipeImage}
    />
  ) : (
    <View accessibilityElementsHidden style={[styles.recipeImage, styles.recipeImagePlaceholder]}>
      <MaterialCommunityIcons color="#BFD9CE" name="bowl-mix-outline" size={42} />
    </View>
  );
}

function RecipeCard({
  isFavorite,
  onFavoritePress,
  onPress,
  recipe,
}: {
  isFavorite: boolean;
  onFavoritePress: () => void;
  onPress?: () => void;
  recipe: MealIdea;
}) {
  return (
    <Pressable
      accessibilityLabel={recipe.title}
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [styles.recipeCard, pressed && styles.pressed]}
    >
      <View style={styles.recipeImageFrame}>
        <RecipeImage recipe={recipe} />
        <Pressable
          accessibilityLabel={isFavorite ? `Remove ${recipe.title} from favorites` : `Favorite ${recipe.title}`}
          accessibilityRole="button"
          accessibilityState={{ selected: isFavorite }}
          hitSlop={6}
          onPress={onFavoritePress}
          style={({ pressed }) => [styles.favoriteButton, pressed && styles.favoritePressed]}
        >
          <MaterialCommunityIcons
            color={COLORS.deepTeal}
            name={isFavorite ? 'heart' : 'heart-outline'}
            size={22}
          />
        </Pressable>
      </View>
      <View style={styles.recipeCardContent}>
        <Text numberOfLines={2} style={styles.recipeTitle}>{recipe.title}</Text>
        <View style={styles.ingredientsRow}>
          {recipe.ingredients.map((ingredient) => (
            <View key={ingredient.name} style={styles.ingredientItem}>
              {ingredient.imageSource ? (
                <Image accessibilityElementsHidden resizeMode="cover" source={ingredient.imageSource} style={styles.ingredientImage} />
              ) : (
                <MaterialCommunityIcons color={COLORS.ingredient} name={ingredient.icon} size={17} />
              )}
              <Text numberOfLines={1} style={styles.ingredientName}>{ingredient.name}</Text>
            </View>
          ))}
        </View>
        <View style={styles.recipeFooter}>
          <View style={[styles.recipeTag, recipe.tagTone === 'green' ? styles.recipeTagGreen : styles.recipeTagBlue]}>
            <Text numberOfLines={1} style={styles.recipeTagText}>{recipe.tag}</Text>
          </View>
          <Text style={styles.recipeTime}>{recipe.time}</Text>
        </View>
      </View>
    </Pressable>
  );
}

export function MealIdeasScreen({ onBack, onRecipePress, recipes = [] }: MealIdeasScreenProps) {
  const [fontsLoaded] = useFonts(priceCheckLocationFontAssets);
  const [selectedCategory, setSelectedCategory] = useState<MealIdeasCategory>('All');
  const [favoriteRecipeIds, setFavoriteRecipeIds] = useState<ReadonlySet<string>>(new Set());
  const filteredRecipes = useMemo(
    () => selectedCategory === 'All'
      ? recipes
      : recipes.filter((recipe) => recipe.categories.includes(selectedCategory)),
    [recipes, selectedCategory],
  );

  const toggleFavorite = (title: string) => {
    setFavoriteRecipeIds((current) => {
      const next = new Set(current);
      if (next.has(title)) {
        next.delete(title);
      } else {
        next.add(title);
      }
      return next;
    });
  };

  if (!fontsLoaded) {
    return <View style={styles.fontLoading} />;
  }

  return (
    <View style={styles.screen}>
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <Pressable
          accessibilityLabel="Back to My Basket"
          accessibilityRole="button"
          onPress={onBack}
          style={({ pressed }) => [styles.headerButton, pressed && styles.pressed]}
        >
          <MaterialCommunityIcons color={COLORS.deepTeal} name="arrow-left" size={29} />
        </Pressable>

        <View style={styles.headerCopy}>
          <Text accessibilityRole="header" style={styles.pageTitle}>Meal ideas</Text>
          <Text style={styles.pageSubtitle}>Browse recipes, with the best matches for your pantry first.</Text>
        </View>

        <ScrollView
          contentContainerStyle={styles.filterRow}
          horizontal
          showsHorizontalScrollIndicator={false}
        >
          {MEAL_IDEAS_CATEGORIES.map((category) => {
            const selected = category === selectedCategory;
            return (
              <Pressable
                accessibilityLabel={`Filter recipes by ${category}`}
                accessibilityRole="button"
                accessibilityState={{ selected }}
                key={category}
              onPress={() => setSelectedCategory(category)}
                style={({ pressed }) => [
                  styles.filterPill,
                  selected ? styles.filterPillSelected : styles.filterPillUnselected,
                  pressed && styles.filterPillPressed,
                ]}
              >
                <Text style={[styles.filterText, selected ? styles.filterTextSelected : styles.filterTextUnselected]}>
                  {category}
                </Text>
              </Pressable>
            );
          })}
        </ScrollView>

        <View accessibilityLabel="Meal idea recipes" style={styles.recipeGrid}>
          {filteredRecipes.map((recipe) => (
            <RecipeCard
              isFavorite={favoriteRecipeIds.has(recipe.title)}
              key={recipe.title}
              onFavoritePress={() => toggleFavorite(recipe.title)}
              onPress={onRecipePress ? () => onRecipePress(recipe) : undefined}
              recipe={recipe}
            />
          ))}
        </View>
      </ScrollView>
    </View>
  );
}

const COLORS = {
  background: '#FEFDFA',
  deepTeal: '#012C2D',
  ingredient: '#2D7463',
  muted: '#486264',
  paleGreen: '#E4F5EA',
  paleMint: '#F2F7F4',
  surface: '#FFFFFF',
  white: '#FFFFFF',
} as const;

const styles = StyleSheet.create({
  content: {
    paddingBottom: 32,
    paddingHorizontal: 24,
    paddingTop: 8,
  },
  favoriteButton: {
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.95)',
    borderColor: '#DCEBE1',
    borderRadius: 18,
    borderWidth: 1,
    height: 34,
    justifyContent: 'center',
    position: 'absolute',
    right: 8,
    top: 8,
    width: 34,
  },
  favoritePressed: {
    opacity: 0.72,
    transform: [{ scale: 0.94 }],
  },
  filterPill: {
    borderRadius: 16,
    minHeight: 40,
    paddingHorizontal: 15,
    alignItems: 'center',
    justifyContent: 'center',
  },
  filterPillPressed: {
    opacity: 0.78,
  },
  filterPillSelected: {
    backgroundColor: COLORS.deepTeal,
  },
  filterPillUnselected: {
    backgroundColor: COLORS.paleMint,
    borderColor: '#E3EDE8',
    borderWidth: 1,
  },
  filterRow: {
    gap: 8,
    paddingBottom: 2,
    paddingTop: 15,
  },
  filterText: {
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 13,
    lineHeight: 17,
  },
  filterTextSelected: {
    color: COLORS.white,
  },
  filterTextUnselected: {
    color: COLORS.deepTeal,
  },
  fontLoading: {
    backgroundColor: COLORS.background,
    flex: 1,
  },
  headerButton: {
    alignItems: 'center',
    height: 48,
    justifyContent: 'center',
    marginLeft: -12,
    width: 48,
  },
  headerCopy: {
    marginTop: 2,
  },
  ingredientItem: {
    alignItems: 'center',
    flexDirection: 'row',
    flexShrink: 1,
    gap: 4,
    minWidth: 0,
  },
  ingredientImage: {
    borderRadius: 9,
    height: 18,
    width: 18,
  },
  ingredientName: {
    color: COLORS.muted,
    flexShrink: 1,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 11,
    lineHeight: 15,
  },
  ingredientsRow: {
    alignItems: 'center',
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 7,
    minHeight: 22,
  },
  pageSubtitle: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 17,
    lineHeight: 22,
    marginTop: 2,
  },
  pageTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.heading,
    fontSize: 35,
    lineHeight: 42,
  },
  pressed: {
    opacity: 0.82,
  },
  recipeCard: {
    backgroundColor: COLORS.surface,
    borderColor: '#DCEBE1',
    borderRadius: 16,
    borderWidth: 1,
    flexBasis: '48%',
    flexGrow: 0,
    minWidth: 0,
    overflow: 'hidden',
  },
  recipeCardContent: {
    gap: 8,
    minHeight: 108,
    padding: 9,
  },
  recipeFooter: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 5,
    justifyContent: 'space-between',
    marginTop: 'auto',
    minWidth: 0,
  },
  recipeGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    paddingTop: 12,
  },
  recipeImage: {
    aspectRatio: 1.82,
    width: '100%',
  },
  recipeImageFrame: {
    position: 'relative',
    width: '100%',
  },
  recipeImagePlaceholder: {
    alignItems: 'center',
    backgroundColor: '#F2F7F4',
    justifyContent: 'center',
  },
  recipeTag: {
    borderRadius: 12,
    flexShrink: 1,
    maxWidth: '62%',
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  recipeTagBlue: {
    backgroundColor: '#E1F0F5',
  },
  recipeTagGreen: {
    backgroundColor: COLORS.paleGreen,
  },
  recipeTagText: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 10.5,
    lineHeight: 15,
  },
  recipeTime: {
    color: COLORS.muted,
    flexShrink: 0,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 11,
    lineHeight: 15,
  },
  recipeTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 16,
    lineHeight: 19,
    minHeight: 38,
  },
  screen: {
    backgroundColor: COLORS.background,
    flex: 1,
  },
});
